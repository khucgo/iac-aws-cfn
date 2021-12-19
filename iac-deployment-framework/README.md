# IaC Deployment Framework

To form repository for individual IaC project.

#### Structure
```yaml
cfn-templates/  : Directory that contains generic CloudFormation templates.
cfn-manifests/  : (Optional) Directory that contains specific CloudFormation templates.
.changes.yaml   : File that contains script for different situation deployments.
.inventory.yaml : File that contains configuration for whole system or environment.
```

#### Engine

- IaC Deployment Engine Lambda
- IaC Deployment Engine Standalone

#### Notes:
- Each repository should only represent an environment or a specific system.

---

## Changes deployment script
File: `.changes.yaml`

#### Description:
Contains script for different situation deployments.

#### Notes:
- Manipulate file `.changes.yaml` for each change deployment.
- Comply the YAML format.
- Refer to structure below to define.
- **IaC Deployment Engine** reads and applies to target environment.
- Items in Changes are executed sequentially from top to bottom.

#### Structure: `.changes.yaml`

**Syntax**
```yaml
Description: (Required) String
Mode: (Required) String
Changes: (Conditional) Sequence of `Objects`
Metadata: (Optional) Mapping or Sequence
```

**Properties**
```yaml
Description:
  - Write about this change for acknowledgement.

Mode:
  - Available options >>
    - 'provision': will provision all according to .inventory.yaml
    - 'destroy': will destroy all according to .inventory.yaml
    - 'on': used when turn on the environment
    - 'off': used when turn off the environment
    - 'change': will process what declared in Changes

Changes:
  - Only effective if Mode is `change`.
  - Sequence of `Objects`.

Metadata:
  - Provide more information relates to this change.
```

**Sample**
```yaml
Description: |-
  CHANGES

Mode: 'provision'

Changes: # In case of Mode: 'change'

Metadata:
  Authors:
    - Quang Vien
```

---

## Inventory
File: `.inventory.yaml`

#### Description:
Contains configuration for whole system or environment.

#### Notes:
- Manipulate file `.inventory.yaml` to maintain the resources of environment.
- Comply the YAML format.
- Refer to structure below to define.
- Referred by `.changes.yaml` when Mode is any of `provision`, `destroy`, `on`, `off`.

#### Structure: `.inventory.yaml`

**Syntax**
```yaml
Description: (Required) String
Inventory: (Required) Sequence of `Objects`
Metadata: (Optional) Mapping or Sequence
```

**Properties**
```yaml
Description:
  - Write about this inventory (environment) for acknowledgement.

Inventory:
  - Sequence of `Objects`.

Metadata:
  - Provide more information relates to this inventory (environment).
```

**Sample**
```yaml
Description: |-
  INVENTORY

Inventory:
  # VPC
  - Object: 'cfn'
    # Conditions: ['provision','destroy']
    Action: ''
    Stack: 'QuangVPC'
    Template: 'cfn-templates/VPC.tpl.yaml'
    Params:
      CidrBlock: '10.30.0.0/19'
      ProjectName: 'iac'
      EnvName: 'demo'

  # Subnet
  - Object: 'cfn'
    Conditions: ['provision','destroy','on','off']
    Action: ''
    Stack: 'QuangVPC-PriSubAccessing'
    Template: 'cfn-templates/Subnet.tpl.yaml'
    Params:
      ImportVpcId: 'QuangVPC::VpcId'
      CidrBlock: '10.30.1.0/24'
      AvailabilityZone: 'eu-central-1a'
      ProjectName: 'iac'
      EnvName: 'demo'

  # AWS API
  - Object: 'aws'
    Conditions: ['provision','on']
    Service: 'eks'
    Action: 'update_cluster_config'
    Params:
      name: 'VPC00-EKS-Cluster-Shared'
      resourcesVpcConfig:
        endpointPublicAccess: True
        endpointPrivateAccess: True

Metadata:
  Maintainers:
    - Quang Vien
```

---

## Objects

#### Description:
2 types:
- cfn: for CloudFormation stack
- aws: for AWS API call using Boto3

#### Notes:
- Replace `<...>` by your desired value.

#### Structure: `cfn` block

**Syntax**
```yaml
Object: 'cfn'
Conditions: (Conditional) Array of string
Action: (Conditional) String
Stack: (Required) String
Template: (Required) String
Params: (Conditional) YAML Mapping or Sequence of mappings
Caps: (Conditional) Array of string
```

**Properties**
```yaml
Object:
  - Must be 'cfn'.

Conditions:
  - Not effective in `change` Mode.
  - If not declare in Inventory, it will be ['provision','destroy'].
  - Available options >>
    - 'provision'
    - 'destroy'
    - 'on'
    - 'off'

Action:
  - Must declare in `change` Mode.
  - Value will be `deploy` if Mode matches Conditionals `provision` or `on`.
  - Value will be `delete` if Mode matches Conditionals `destroy` or `off`.

Stack:
  - Stack's name that will be manipulated.

Template:
  - Relative path to the CloudFormation template.
  - Unix-style path.

Params:
  - Stands for Parameters.
  - Support both YAML format (Mapping and Sequence).
  - Depends on the Template's requirements OR demand.
  - Mapping format >>
      <param name|refer to template>: '<param value|input your desire>'
  - Sequence format >>
      Array of mapping format >>
        Name: '<param name|refer to template>'
        Value: '<param value|input your desire>'

Caps:
  - Stands for Capabilities.
  - Depends on the Template's requirements.
  - Avalable options >>
    - 'CAPABILITY_IAM'
    - 'CAPABILITY_NAMED_IAM'
    - 'CAPABILITY_AUTO_EXPAND'
```

**Sample**
```yaml
  - Object: 'cfn'
    Conditions: ['provision','destroy','on','off']
    Action: ''
    Stack: 'VPC00-EKS-Cluster-Shared'
    Template: 'cfn-templates/EKS/EKS_Cluster.tpl.yaml'
    Params:
      ImportVpcId: 'VPC00::VpcId'
      ImportSubnetIds: 'VPC00-PriSubProcessing-A::SubnetId,VPC00-PriSubProcessing-B::SubnetId'
      Version: '1.19'
    Caps:
      - CAPABILITY_IAM
```

#### Structure: `aws` block

**Syntax**
```yaml
Object: 'aws'
Conditions: (Conditional) Array of string
Service: (Required) String
Action: (Required) String
Params: (Conditional) YAML format for Python dict
```

**Properties**
```yaml
Object:
  - Must be 'aws'.

Conditions:
  - Not effective in `change` Mode.
  - If not declare in Inventory, object will be skipped.
  - Available options >>
    - 'provision'
    - 'destroy'
    - 'on'
    - 'off'

Service:
  - Must be supported by Boto3.
  - Reference for available services here https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html.

Action:
  - The available method of the Service's Client member.

Params:
  - Stands for Parameters.
  - Depends on the method OR demand.
```

**Sample**
```yaml
  # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/eks.html#EKS.Client.update_cluster_config
  - Object: 'aws'
    Conditions: ['provision','on']
    Service: 'eks'
    Action: 'update_cluster_config'
    Params:
      name: 'VPC00-EKS-Cluster-Shared'
      resourcesVpcConfig:
        endpointPrivateAccess: True

```
