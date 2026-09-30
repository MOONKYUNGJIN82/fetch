"""Use bundled trust roots without disabling TLS verification."""
import ssl
import certifi


def tls_context():
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context
