# IAM Role per EC2 (CloudWatch Logs) — gestito MANUALMENTE dalla console AWS,
# NON da Terraform (l'utente hopcraft-deploy non ha permessi IAM).
#
# Setup effettuato una-tantum via console come root:
#   - Ruolo: hopcraft-ec2-role  (EC2 trust policy)
#   - Policy: CloudWatchLogsFullAccess
#   - Instance profile: hopcraft-ec2-role (attaccato all'istanza EC2)
#
# Il driver awslogs di Docker usa le credenziali del ruolo via EC2 metadata service.
