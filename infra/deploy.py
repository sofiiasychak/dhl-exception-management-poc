from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REGION = os.getenv("AWS_REGION", "eu-central-1")
STACK = os.getenv("STACK_NAME", "exception-management-poc")


def run(
    command: list[str],
    *,
    capture: bool = False,
    env: dict | None = None,
    cwd: Path | None = None,
) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        env=env,
        cwd=cwd,
    )
    return result.stdout.strip() if capture else ""


def aws(*args: str, capture: bool = False) -> str:
    return run(["aws", *args, "--region", REGION], capture=capture)


def lambda_archive(temp: Path) -> Path:
    package_dir = temp / "package"
    package_dir.mkdir()
    backend = ROOT / "backend"
    run([
        "docker", "run", "--rm", "--platform", "linux/amd64",
        "-v", f"{backend}:/src:ro",
        "-v", f"{package_dir}:/out",
        "python:3.12-slim",
        "sh", "-c",
        "pip install --quiet --no-cache-dir -r /src/requirements-lambda.txt -t /out "
        "&& cp -R /src/app /out/app",
    ])
    archive = temp / "lambda.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path in package_dir.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                zip_file.write(path, path.relative_to(package_dir))
    return archive


def stack_output(key: str) -> str:
    return aws(
        "cloudformation", "describe-stacks", "--stack-name", STACK,
        "--query", f"Stacks[0].Outputs[?OutputKey==`{key}`].OutputValue | [0]",
        "--output", "text", capture=True,
    )


def main():
    if REGION != "eu-central-1":
        raise SystemExit("This PoC is configured for eu-central-1; set AWS_REGION=eu-central-1.")
    if shutil.which("aws") is None or shutil.which("docker") is None:
        raise SystemExit("Install AWS CLI and Docker before deploying.")

    account = aws("sts", "get-caller-identity", "--query", "Account", "--output", "text", capture=True)
    bucket = os.getenv("DEPLOYMENT_BUCKET") or f"exception-management-artifacts-{account}-{REGION}"
    try:
        aws("s3api", "head-bucket", "--bucket", bucket)
    except subprocess.CalledProcessError:
        if REGION == "us-east-1":
            aws("s3api", "create-bucket", "--bucket", bucket)
        else:
            aws(
                "s3api", "create-bucket", "--bucket", bucket,
                "--create-bucket-configuration", f"LocationConstraint={REGION}",
            )
        aws(
            "s3api", "put-public-access-block", "--bucket", bucket,
            "--public-access-block-configuration",
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true",
        )

    frontend = ROOT / "frontend"
    with tempfile.TemporaryDirectory(
        prefix=".build-", dir=ROOT
    ) as directory:
        archive = lambda_archive(Path(directory))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()[:16]
        key = f"lambda/exception-management-{digest}.zip"
        aws("s3", "cp", str(archive), f"s3://{bucket}/{key}")
        run(["npm", "ci"], cwd=frontend)
        run(
            ["npm", "run", "build"],
            cwd=frontend,
            env={**os.environ, "VITE_API_BASE_URL": "/api", "VITE_LOCAL_DEMO_LOGIN": "false"},
        )

    aws(
        "cloudformation", "deploy",
        "--template-file", str(ROOT / "infra" / "template.yaml"),
        "--stack-name", STACK,
        "--capabilities", "CAPABILITY_IAM",
        "--parameter-overrides", f"DeploymentBucket={bucket}", f"LambdaObjectKey={key}",
    )
    site_bucket = stack_output("SiteBucketName")
    distribution_id = stack_output("DistributionId")
    aws("s3", "sync", str(frontend / "dist"), f"s3://{site_bucket}", "--delete")
    aws("cloudfront", "create-invalidation", "--distribution-id", distribution_id, "--paths", "/*")
    print(f"Deployed: {stack_output('SiteUrl')}")
    print(f"Cognito User Pool: {stack_output('UserPoolId')}")


if __name__ == "__main__":
    main()
