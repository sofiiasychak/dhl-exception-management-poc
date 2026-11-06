from __future__ import annotations

import os
import subprocess


REGION = os.getenv("AWS_REGION", "eu-central-1")
STACK = os.getenv("STACK_NAME", "exception-management-poc")


def aws(*args: str, capture: bool = False):
    result = subprocess.run(
        ["aws", *args, "--region", REGION],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def main():
    site_bucket = aws(
        "cloudformation", "describe-stacks", "--stack-name", STACK,
        "--query", "Stacks[0].Outputs[?OutputKey==`SiteBucketName`].OutputValue | [0]",
        "--output", "text", capture=True,
    )
    evidence_bucket = aws(
        "cloudformation", "describe-stacks", "--stack-name", STACK,
        "--query", "Stacks[0].Outputs[?OutputKey==`EvidenceBucketName`].OutputValue | [0]",
        "--output", "text", capture=True,
    )
    if site_bucket and site_bucket != "None":
        aws("s3", "rm", f"s3://{site_bucket}", "--recursive")
    aws("cloudformation", "delete-stack", "--stack-name", STACK)
    aws("cloudformation", "wait", "stack-delete-complete", "--stack-name", STACK)
    print(f"Deleted stack {STACK}.")
    if evidence_bucket and evidence_bucket != "None":
        print(f"Evidence bucket retained to preserve uploaded photos: {evidence_bucket}")


if __name__ == "__main__":
    main()
