# Release notes
Name: IaC Deployment Engine Lambda

Shortname: IDEL

---
### v0.1.4
- Handle empty `Params` in `aws` object.

### v0.1.3
- Fix issue related to missing `Action` in `cfn` object.

### v0.1.2
- Print total number of objects (blocks) that processing.

### v0.1.1
- Make RoleARN optional

### v0.1
(bumped version)
- Support `aws` block.
- Support 2 extra modes: `on`, `off`.
- Refactor documentation (README) to improve readability.

### v0.0.5
- Support mapping format in Params (cfn) for better view

### v0.0.4
- Support Mode(s): change/provision/destroy

### v0.0.3
- Fix issue when delete non-existing CloudFormation stack

### v0.0.2
- Fix issue when update unchanged CloudFormation stack

### v0.0.1
- It just works by supporting CloudFormation templates.
