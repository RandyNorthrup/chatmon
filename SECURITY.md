# Security

## Reporting a problem

Please report a security problem privately, as a
[security advisory](https://github.com/RandyNorthrup/chatmon/security/advisories/new), rather than as an issue.
An advisory stays between you and the maintainer until a release with the fix is out.

Say what you found, which version (`chatmon --version`) and system, and how to make it happen if you know. Leave
out real API keys and chats. Replies, and the fix, are discussed on the advisory, and you're credited when it's
published if you'd like to be.

## Which versions get fixes

The latest release. Fixes go into the next release; there are no maintenance branches. Chatmon 0.6.0 and later
update themselves (**Help & updates** in the menu).

## What counts

Anything that breaks a promise in the README's [Privacy and security](README.md#privacy-and-security) section.
For example:

- another user or program on your computer reaching Chatmon, or acting as you through it;
- a key, a chat or a file leaving your computer other than to the brain you chose;
- an update that installs without the release key's signature;
- an agent's hooks being changed without your say.

The installers, the updater and the release workflow ([packages.yml](.github/workflows/packages.yml)) count too.

## Checking a download

Each release lists every file's SHA-256 checksum in `SHA256SUMS.txt`, signed with Chatmon's release key
(`SHA256SUMS.txt.sig`, Ed25519). Chatmon's updater installs nothing that isn't in a list that key signed. The
Windows installer is also signed by Randy Northrup (Authenticode).

From 0.10.0 on, each file also has a build provenance attestation from the GitHub Actions run that built it. The
GitHub CLI checks one and says which workflow, commit and tag made the file:

```sh
gh attestation verify chatmon_0.10.0-1_all.deb --repo RandyNorthrup/chatmon
```
