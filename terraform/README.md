# Terraform Configurations

## AWS (Primary)

Deploy OpenContext to AWS Lambda. See [Deployment Guide](../docs/DEPLOYMENT.md).

```bash
cd aws
terraform init
terraform plan -var="config_file=../../config.yaml"
terraform apply
```

## Other Clouds

- **GCP:** [gcp/](gcp/) – Coming soon
- **Azure:** [azure/](azure/) – Coming soon
