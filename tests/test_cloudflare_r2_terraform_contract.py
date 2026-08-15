from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "infra" / "cloudflare" / "r2-public-domain"


def text(name: str) -> str:
    return (MODULE / name).read_text(encoding="utf-8")


def test_publication_contract_is_semantic_not_duplicate_dns() -> None:
    main = text("main.tf")
    assert 'resource "cloudflare_r2_custom_domain" "domain"' in main
    assert "cloudflare_dns_record" not in main
    assert "enabled      = true" in main


def test_r2_dev_is_explicit_and_defaults_disabled() -> None:
    main = text("main.tf")
    variables = text("variables.tf")
    assert 'resource "cloudflare_r2_managed_domain" "r2_dev"' in main
    assert "enabled      = var.enable_r2_dev" in main
    marker = 'variable "enable_r2_dev"'
    block = variables[variables.index(marker) :]
    assert "default     = false" in block


def test_bucket_destroy_requires_code_change() -> None:
    assert "prevent_destroy = true" in text("main.tf")


def test_existing_custom_domain_has_read_only_mode() -> None:
    main = text("main.tf")
    variables = text("variables.tf")
    assert 'variable "manage_custom_domain"' in variables
    assert 'data "cloudflare_r2_custom_domain" "existing_domain"' in main


def test_jurisdiction_is_propagated() -> None:
    main = text("main.tf")
    variables = text("variables.tf")
    assert 'variable "jurisdiction"' in variables
    assert "jurisdiction  = local.jurisdiction" in main
    assert 'contains(["default", "eu", "fedramp"]' in variables


def test_provider_and_secret_boundary() -> None:
    versions = text("versions.tf")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in MODULE.glob("*.tf"))
    assert 'version = "~> 5.22.0"' in versions
    assert "api_token" not in combined
    assert "CLOUDFLARE_API_TOKEN" in versions


def test_apply_requires_explicit_publication_authorization() -> None:
    script = text("run.sh")
    assert "--authorize-publication" in script
    assert "terraform apply -input=false tfplan" in script


def test_readme_matches_current_import_boundary() -> None:
    readme = text("README.md")
    assert "does not support Terraform import" in readme
    assert "cloudflare_r2_bucket.bucket" in readme
