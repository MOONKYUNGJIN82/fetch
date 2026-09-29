"""Prepare a temporary CI keychain without logging credential values."""
import base64
import os
from pathlib import Path
import secrets
import subprocess
import urllib.request


def run(*args):
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f'Signing setup failed: {Path(args[0]).name} {args[1]}') from error


def main():
    required = ('MACOS_CERTIFICATE_P12_BASE64', 'MACOS_CERTIFICATE_PASSWORD',
                'APPLE_API_KEY_P8_BASE64', 'APPLE_API_KEY_ID', 'APPLE_API_ISSUER',
                'RUNNER_TEMP', 'GITHUB_ENV')
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError('Missing signed-release configuration: ' + ', '.join(missing))
    temp = Path(os.environ['RUNNER_TEMP'])
    certificate = temp / 'fetch-developer-id.p12'
    key = temp / f"AuthKey_{os.environ['APPLE_API_KEY_ID']}.p8"
    chain = temp / 'DeveloperIDG2CA.cer'
    keychain = temp / 'fetch-signing.keychain-db'
    certificate.write_bytes(base64.b64decode(os.environ['MACOS_CERTIFICATE_P12_BASE64'], validate=True))
    certificate.chmod(0o600)
    key.write_bytes(base64.b64decode(os.environ['APPLE_API_KEY_P8_BASE64'], validate=True))
    key.chmod(0o600)
    urllib.request.urlretrieve('https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer', chain)
    password = secrets.token_urlsafe(32)
    run('security', 'create-keychain', '-p', password, str(keychain))
    run('security', 'set-keychain-settings', '-lut', '21600', str(keychain))
    run('security', 'unlock-keychain', '-p', password, str(keychain))
    run('security', 'import', str(certificate), '-k', str(keychain),
        '-P', os.environ['MACOS_CERTIFICATE_PASSWORD'], '-T', '/usr/bin/codesign')
    run('security', 'import', str(chain), '-k', str(keychain))
    current = run('security', 'list-keychains', '-d', 'user').replace('"', '').split()
    run('security', 'list-keychains', '-d', 'user', '-s', *current, str(keychain))
    run('security', 'set-key-partition-list', '-S', 'apple-tool:,apple:,codesign:',
        '-s', '-k', password, str(keychain))
    identity = 'Developer ID Application: KALLOS Co., Ltd. (9B435Z7M2H)'
    if identity not in run('security', 'find-identity', '-v', '-p', 'codesigning', str(keychain)):
        raise RuntimeError('Expected KALLOS Developer ID signing identity not available')
    with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as env:
        env.write(f'MAC_SIGN_IDENTITY={identity}\n')
        env.write(f'APPLE_API_KEY={key}\n')
    print('KALLOS Developer ID signing and Apple notarization credentials ready')


if __name__ == '__main__':
    main()
