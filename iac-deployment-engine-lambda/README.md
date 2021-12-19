# IaC Deployment Engine Lambda (IDEL)

**Lambda** variation of **I**aC **D**eployment **E**ngine

To deploy IaC repository that follows **IaC Deployment Framework** (repository `iac-deployment-framework`).

---

## Manual

#### How to setup an IDEL?

**IDEL** runs in a CodePipeline pipeline. So, to implement, the following resources are provisioned:
- A CodePipeline
- A Lambda function to deploy IDEL then serve the `Deploy` stage in CodePipeline
- An EventBridge rule to watch on the target IaC CodeCommit repository then trigger CodePipeline
- (Optional) An SNS topic to notify the Manual Approval

A list of implemented **IDEL** pipelines is tracked in `implemented-idel-pipelines`. Please refer to that repository for real cases. :)

--

#### How to on-demand deploy the Lambda function?

**Notice:**
- Only do this if you understand the IDEL's flow.
- The CodePipeline pipeline always points to the latest version of the Lambda function.
- The Lambda function codebase should be deployed and kept track in a repository like `implemented-idel-pipelines`.

**Steps:**

1. Open PowerShell
2. Change dir to the directory of `deploy.ps1`
3. Execute below command:
    ```powershell
    .\deploy.ps1 <function_name> <local_aws_named_profile>
    ```

--

#### How it works?

The engine:

1. Looks into the IaC repository.
2. Loads `.changes.yaml`.
3. Loads `.inventory.yaml` and/or files in `cfn-templates/`/`cfn-manifests/` depends on the declaration.
4. Transforms to AWS APIs and call to target AWS environment (Boto3 bts).

--

#### Environment Variables

For the Lambda function:

| Name                 | Value                             | Comment                                                                  |
|----------------------|-----------------------------------|--------------------------------------------------------------------------|
| `ARTIFACT_DIR`       | `/tmp/artifact/`                  | Default path to store IaC repository in the instance of Lambda function. |
| `CHANGES_FILE`       | `.changes.yaml`                   | Default `changes` file in IaC repository.                                |
| `SECRET_NAME`        | `REPLACE_SECRET_NAME_HERE`        | Name of secret stored in Secrets Manager.                                |
| `LOGGING_LEVEL`      | `INFO`                            | Possible values are INFO, ERROR, DEBUG                                   |
| `WAITING_OCCURRENCE` | `5`                               | Max number of Lambda function execution round to process waiting.        |
| `CFN_WAITER_CONFIG`  | `{"Delay": 5,"MaxAttempts": 120}` | Wait configuration for CloudFormation stack.                             |

--

#### Secret

IDEL uses credential (IAM) which is stored in Secrets Manager to access target environment. A secret contains:

| Key                 | Desired Value                                                                     |
|---------------------|-----------------------------------------------------------------------------------|
| `ACCOUNT_NUMBER`    | (Required) AWS account id (not alias).                                            |
| `ACCESS_KEY_ID`     | (Required) Of IAM account on target AWS account.                                  |
| `SECRET_ACCESS_KEY` | (Required) Of IAM account on target AWS account.                                  |
| `REGION`            | (Required) Of target AWS account.                                                 |
| `OUTPUT_FORMAT`     | (Optional) yaml\|json\|text                                                       |
| `ROLE_NAME`         | (Optional) Of IAM Role to manipulate CloudFormation stacks on target AWS account. |

---
