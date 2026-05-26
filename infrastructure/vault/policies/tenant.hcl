path "secret/data/platform/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/data/tenants/*" {
  capabilities = ["read", "list"]
}

path "secret/data/tenants/{{identity.entity.id}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
