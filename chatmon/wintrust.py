"""Windows: who signed a file, as Windows' own Authenticode check sees it, through Windows' own libraries alone
(nothing has to start: a company that blocks PowerShell doesn't stop it).

WinVerifyTrust checks the file's own signature and its certificate's chain (WINTRUST_ACTION_GENERIC_VERIFY_V2,
the Authenticode policy), including whether any certificate in the chain has been revoked, and the signer's
certificate is read from the very state it checked: no second look at the file. A revocation that can't be
looked up (no connection to the certificate's servers) is its own answer, never "Valid". Only a signature in the
file itself counts: a catalog of Windows' own, which vouches for Windows' programs, never vouches for a
download. `hold` keeps a file as it is while it's checked and run. Imported on Windows alone.
https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust
https://learn.microsoft.com/en-us/windows/win32/seccrypto/example-c-program--verifying-the-signature-of-a-pe-file
https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-wthelperprovdatafromstatedata
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


WINTRUST_ACTION_GENERIC_VERIFY_V2 = GUID(0x00AAC56B, 0xCD44, 0x11D0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
WTD_UI_NONE, WTD_REVOKE_NONE, WTD_REVOKE_WHOLECHAIN, WTD_CHOICE_FILE = 2, 0, 1, 1
WTD_STATEACTION_VERIFY, WTD_STATEACTION_CLOSE = 1, 2
WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT = 0x80  # every certificate but the root, which no one can revoke
# Holding a file: open to read, sharing reading alone, so nobody can write, rename or delete it meanwhile.
GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL = 0x80000000, 0x1, 3, 0x80
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1)  # no one to ask: never any UI
CERT_NAME_RDN_TYPE, CERT_NAME_ISSUER_FLAG = 2, 1
CERT_X500_NAME_STR, CERT_NAME_STR_REVERSE_FLAG = 3, 0x02000000  # "CN=..., O=..., C=US", as .NET's Subject reads
CERT_FIND_EXT_ONLY_ENHKEY_USAGE_FLAG = 0x2  # the certificate's own extension, never a property set on this PC

# WinVerifyTrust's answers, in Get-AuthenticodeSignature's words.
STATUS = {
    0: "Valid",
    0x800B0100: "NotSigned",  # TRUST_E_NOSIGNATURE
    0x800B0003: "NotSupportedFileFormat",  # TRUST_E_SUBJECT_FORM_UNKNOWN
    0x800B0001: "NotSupportedFileFormat",  # TRUST_E_PROVIDER_UNKNOWN
    0x80096010: "HashMismatch",  # TRUST_E_BAD_DIGEST: changed since it was signed
    0x80096001: "HashMismatch",  # TRUST_E_SYSTEM_ERROR, as a damaged signature gives it
    0x8009200D: "HashMismatch",  # CRYPT_E_BAD_MSG
    0x800B0109: "NotTrusted",  # CERT_E_UNTRUSTEDROOT
    0x800B010A: "NotTrusted",  # CERT_E_CHAINING
    0x800B0111: "NotTrusted",  # TRUST_E_EXPLICIT_DISTRUST
    0x800B010C: "Revoked",  # CERT_E_REVOKED: a certificate in its chain has been revoked
    0x80092010: "Revoked",  # CRYPT_E_REVOKED
    0x80092013: "RevocationUnknown",  # CRYPT_E_REVOCATION_OFFLINE: its servers couldn't be reached
    0x80092012: "RevocationUnknown",  # CRYPT_E_NO_REVOCATION_CHECK
    0x800B010E: "RevocationUnknown",  # CERT_E_REVOCATION_FAILURE
    0x800B0101: "NotTrusted",  # CERT_E_EXPIRED
    0x80096019: "NotTrusted",  # TRUST_E_BASIC_CONSTRAINTS
    0x800B010F: "NotTrusted",  # CERT_E_CN_NO_MATCH
}


class WINTRUST_FILE_INFO(ctypes.Structure):
    _fields_ = [("cbStruct", wintypes.DWORD), ("pcwszFilePath", wintypes.LPCWSTR), ("hFile", wintypes.HANDLE),
                ("pgKnownSubject", ctypes.POINTER(GUID))]


class WINTRUST_DATA(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("pPolicyCallbackData", ctypes.c_void_p),
        ("pSIPClientData", ctypes.c_void_p),
        ("dwUIChoice", wintypes.DWORD),
        ("fdwRevocationChecks", wintypes.DWORD),
        ("dwUnionChoice", wintypes.DWORD),
        ("pFile", ctypes.POINTER(WINTRUST_FILE_INFO)),
        ("dwStateAction", wintypes.DWORD),
        ("hWVTStateData", wintypes.HANDLE),
        ("pwszURLReference", wintypes.LPWSTR),
        ("dwProvFlags", wintypes.DWORD),
        ("dwUIContext", wintypes.DWORD),
        ("pSignatureSettings", ctypes.c_void_p),
    ]


class CRYPT_PROVIDER_CERT(ctypes.Structure):  # its first fields: the certificate is all that's read
    _fields_ = [("cbStruct", wintypes.DWORD), ("pCert", ctypes.c_void_p)]


class CERT_ENHKEY_USAGE(ctypes.Structure):
    _fields_ = [("cUsageIdentifier", wintypes.DWORD), ("rgpszUsageIdentifier", ctypes.POINTER(ctypes.c_char_p))]


_wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_CreateFile = _kernel32.CreateFileW
_CreateFile.restype = wintypes.HANDLE
_CreateFile.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
_CloseHandle = _kernel32.CloseHandle
_CloseHandle.restype, _CloseHandle.argtypes = wintypes.BOOL, [wintypes.HANDLE]
INVALID_HANDLE = ctypes.c_void_p(-1).value

_WinVerifyTrust = _wintrust.WinVerifyTrust
_WinVerifyTrust.restype, _WinVerifyTrust.argtypes = wintypes.LONG, [wintypes.HANDLE, ctypes.POINTER(GUID), ctypes.POINTER(WINTRUST_DATA)]
_ProvData = _wintrust.WTHelperProvDataFromStateData
_ProvData.restype, _ProvData.argtypes = ctypes.c_void_p, [wintypes.HANDLE]
_ProvSigner = _wintrust.WTHelperGetProvSignerFromChain
_ProvSigner.restype, _ProvSigner.argtypes = ctypes.c_void_p, [ctypes.c_void_p, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_ProvCert = _wintrust.WTHelperGetProvCertFromChain
_ProvCert.restype, _ProvCert.argtypes = ctypes.POINTER(CRYPT_PROVIDER_CERT), [ctypes.c_void_p, wintypes.DWORD]
_NameString = _crypt32.CertGetNameStringW
_NameString.restype = wintypes.DWORD
_NameString.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD]
_KeyUsage = _crypt32.CertGetEnhancedKeyUsage
_KeyUsage.restype = wintypes.BOOL
_KeyUsage.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]


def _name(cert: int, issuer: bool) -> str:
    kind = wintypes.DWORD(CERT_X500_NAME_STR | CERT_NAME_STR_REVERSE_FLAG)
    flags = CERT_NAME_ISSUER_FLAG if issuer else 0
    size = _NameString(cert, CERT_NAME_RDN_TYPE, flags, ctypes.byref(kind), None, 0)
    if size <= 1:
        return ""
    buffer = ctypes.create_unicode_buffer(size)
    _NameString(cert, CERT_NAME_RDN_TYPE, flags, ctypes.byref(kind), buffer, size)
    return buffer.value


def _usages(cert: int) -> list[str]:
    size = wintypes.DWORD(0)
    if not _KeyUsage(cert, CERT_FIND_EXT_ONLY_ENHKEY_USAGE_FLAG, None, ctypes.byref(size)) or not size.value:
        return []
    buffer = (ctypes.c_byte * size.value)()
    if not _KeyUsage(cert, CERT_FIND_EXT_ONLY_ENHKEY_USAGE_FLAG, buffer, ctypes.byref(size)):
        return []
    usage = CERT_ENHKEY_USAGE.from_buffer(buffer)
    return [usage.rgpszUsageIdentifier[i].decode("ascii", errors="replace") for i in range(usage.cUsageIdentifier)]


def hold(path: Path) -> int:
    """A handle that keeps the file as it is until `release`: opened to read, sharing nothing but reading, so
    nobody (Chatmon included) can write to it, rename it, delete it, or rename the folder it's in. A program can
    still be started from it, and anything can still read it. OSError if it can't be opened."""
    handle = _CreateFile(str(path), GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if handle in (None, INVALID_HANDLE):
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def release(handle: int) -> None:
    _CloseHandle(handle)


def signer(path: Path) -> tuple[str, str, str, list[str]]:
    """(status, signer, issuer, extended key usages) of the file's own Authenticode signature: status in
    Get-AuthenticodeSignature's words ("Valid", "NotSigned", "HashMismatch", "NotTrusted"...), or "Revoked"
    (a certificate in its chain has been) or "RevocationUnknown" (that couldn't be looked up), the rest from
    the signer's certificate, as .NET writes a certificate's Subject and Issuer. Can take a while (Windows may
    fetch what the certificate chain needs, and whether it's been revoked): off the screen's thread."""
    info = WINTRUST_FILE_INFO(ctypes.sizeof(WINTRUST_FILE_INFO), str(path), None, None)
    data = WINTRUST_DATA()
    data.cbStruct = ctypes.sizeof(WINTRUST_DATA)
    data.dwUIChoice = WTD_UI_NONE
    data.fdwRevocationChecks = WTD_REVOKE_WHOLECHAIN
    data.dwProvFlags = WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT
    data.dwUnionChoice = WTD_CHOICE_FILE
    data.pFile = ctypes.pointer(info)
    data.dwStateAction = WTD_STATEACTION_VERIFY
    action = GUID.from_buffer_copy(WINTRUST_ACTION_GENERIC_VERIFY_V2)
    code = _WinVerifyTrust(INVALID_HANDLE_VALUE, ctypes.byref(action), ctypes.byref(data)) & 0xFFFFFFFF
    try:
        name = issuer = ""
        usages: list[str] = []
        provider = _ProvData(data.hWVTStateData) if data.hWVTStateData else None
        signer_ = _ProvSigner(provider, 0, False, 0) if provider else None
        cert = _ProvCert(signer_, 0) if signer_ else None
        if cert and cert.contents.pCert:  # a signature's there, checked or not: whose it is says why it failed
            name, issuer, usages = _name(cert.contents.pCert, False), _name(cert.contents.pCert, True), _usages(cert.contents.pCert)
    finally:
        data.dwStateAction = WTD_STATEACTION_CLOSE
        _WinVerifyTrust(INVALID_HANDLE_VALUE, ctypes.byref(action), ctypes.byref(data))
    return STATUS.get(code, f"UnknownError (0x{code:08X})"), name, issuer, usages
