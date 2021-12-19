# Release notes
Name: IaC Deployment Engine Standalone

Shortname: IDES

---
### v0.1.4
(bumped version to be the same as IDEL)
- Handle empty `Params` in `aws` object.

### v0.1.1
- Fix issue related to missing `Action` in `cfn` object.

### v0.1
(bumped version)
- Support `aws` block the same as IDEL works.
- Support 2 extra modes: `on`, `off`.
- Refactor documentation (README) to improve readability.

### v0.0.10
- Support mapping format in Params (cfn) for better view

### v0.0.9
- Fix issue with number-type params

### v0.0.8
- Support Mode(s): change/provision/destroy

### v0.0.7
- Support using environment variables to override local ones: CFN_ROLE_ARN

### v0.0.6
- CloudFormation: support Capabilities
- CloudFormation: drop supporting Options

### v0.0.5
- Support AWS CLI

### v0.0.4
- CloudFormation: support Options to extend

### v0.0.3
- Housekeeping

### v0.0.2
- CloudFormation: wait for stack complete

### v0.0.1
- It just works by support CloudFormation templates.
