"""API keys kept in your system's own keychain, so they needn't sit in an environment variable or a file.

Windows keeps them in the Credential Manager (on this computer only, never roaming), macOS in your login Keychain,
and Linux in the Secret Service your desktop runs (GNOME Keyring, KWallet, KeePassXC). Nothing new is installed for
it: ctypes reaches Windows' and Apple's own libraries, and QtDBus the Secret Service.

Each key is kept under the name of the brain it's for ("anthropic-api"). A key is never logged, printed, or put in
an error message, and it's never part of a backup (backup.py). On Linux the key travels to the keyring over your own
session bus, which only you can reach, in the Secret Service's "plain" session: its encrypted one needs
Diffie-Hellman and AES, which Python's own library doesn't have.
"""

from __future__ import annotations

import sys

SERVICE = "chatmon"  # what each entry is filed under, with the brain's name


class KeychainError(Exception):
    """The keychain couldn't be used: a sentence saying why, never holding the key."""


class InMemory:
    """A keychain held in memory only (tests, and a computer with no keychain at all)."""

    name = "memory only"

    def __init__(self):
        self.keys: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.keys.get(name)

    def has(self, name: str) -> bool:
        return name in self.keys

    def set(self, name: str, secret: str) -> None:
        self.keys[name] = secret

    def delete(self, name: str) -> None:
        self.keys.pop(name, None)


_store = None
_cache: dict[str, str | None] = {}  # keys read this run, by brain: each is read once
_present: dict[str, bool] = {}  # whether one is saved, by brain: the menu asks after every brain each time it opens


def use(store) -> object:
    """Keep keys in `store` from now on (None: the system's own); returns the one used until now."""
    global _store
    before, _store = _store, store
    _cache.clear()
    _present.clear()
    return before


def _the_store():
    global _store
    if _store is None:
        if sys.platform == "win32":
            _store = _Windows()
        elif sys.platform == "darwin":
            _store = _Mac()
        else:
            _store = _SecretService()
    return _store


def where() -> str:
    """Where keys are kept on this computer, for Settings to say."""
    return _the_store().name


def has(name: str) -> bool:
    """Is a key saved for the brain `name`? Found without reading the key itself, so the menu never sets off the
    macOS Keychain's "Chatmon wants to use…" question; that waits for the first question actually asked."""
    if _cache.get(name):
        return True
    if name not in _present:
        try:
            _present[name] = bool(_the_store().has(name))
        except (KeychainError, OSError):
            _present[name] = False
    return _present[name]


def get(name: str) -> str | None:
    """The key saved for the brain `name`, or None: none saved, or the keychain can't be reached (or is locked)."""
    if name in _cache:
        return _cache[name]
    try:
        found = _the_store().get(name)
    except (KeychainError, OSError):
        found = None
    _cache[name] = found or None
    _present[name] = _cache[name] is not None
    return _cache[name]


def set(name: str, secret: str) -> str | None:
    """Save `secret` as the key for the brain `name`, replacing any; None when it's saved, else why not."""
    secret = secret.strip()
    if not secret:
        return delete(name)
    try:
        _the_store().set(name, secret)
    except (KeychainError, OSError) as exc:
        _cache.pop(name, None)
        _present.pop(name, None)
        return str(exc) or "the keychain couldn't save it"
    _cache[name], _present[name] = secret, True
    return None


def delete(name: str) -> str | None:
    """Forget the key saved for the brain `name` (nothing saved is no problem); None when it's gone, else why not."""
    try:
        _the_store().delete(name)
    except (KeychainError, OSError) as exc:
        _cache.pop(name, None)
        _present.pop(name, None)
        return str(exc) or "the keychain couldn't remove it"
    _cache[name], _present[name] = None, False
    return None


# -- Windows: the Credential Manager


class _Windows:
    name = "Windows Credential Manager"
    TYPE_GENERIC = 1
    PERSIST_LOCAL_MACHINE = 2  # this computer, for you; never the domain's roaming copy
    ERROR_NOT_FOUND = 1168
    MAX_BLOB = 5 * 512  # CRED_MAX_CREDENTIAL_BLOB_SIZE

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class FileTime(ctypes.Structure):
            _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

        class Credential(ctypes.Structure):  # CREDENTIALW
            _fields_ = [
                ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                ("LastWritten", FileTime), ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
            ]

        self.ctypes, self.Credential = ctypes, Credential
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.read = advapi32.CredReadW
        self.read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
        self.read.restype = wintypes.BOOL
        self.write = advapi32.CredWriteW
        self.write.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        self.write.restype = wintypes.BOOL
        self.remove = advapi32.CredDeleteW
        self.remove.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.remove.restype = wintypes.BOOL
        self.free = advapi32.CredFree
        self.free.argtypes = [ctypes.c_void_p]

    @staticmethod
    def target(name: str) -> str:
        return f"{SERVICE}:{name}"

    def get(self, name: str) -> str | None:
        ctypes = self.ctypes
        found = ctypes.POINTER(self.Credential)()
        if not self.read(self.target(name), self.TYPE_GENERIC, 0, ctypes.byref(found)):
            if ctypes.get_last_error() == self.ERROR_NOT_FOUND:
                return None
            raise KeychainError(f"the Credential Manager couldn't be read (error {ctypes.get_last_error()})")
        try:
            blob = ctypes.string_at(found.contents.CredentialBlob, found.contents.CredentialBlobSize)
        finally:
            self.free(found)
        return blob.decode("utf-16-le", "replace") or None

    def has(self, name: str) -> bool:
        return self.get(name) is not None  # Windows never asks you anything to read your own

    def set(self, name: str, secret: str) -> None:
        ctypes = self.ctypes
        blob = secret.encode("utf-16-le")  # how Windows' own tools (cmdkey, the control panel) keep a password
        if len(blob) > self.MAX_BLOB:
            raise KeychainError(f"that key is too long for the Credential Manager ({self.MAX_BLOB // 2} characters at most)")
        data = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        credential = self.Credential()
        credential.Type = self.TYPE_GENERIC
        credential.TargetName = self.target(name)
        credential.Comment = f"Chatmon: the API key for {name}"
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(data, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = self.PERSIST_LOCAL_MACHINE
        credential.UserName = name
        if not self.write(ctypes.byref(credential), 0):
            raise KeychainError(f"the Credential Manager couldn't save it (error {ctypes.get_last_error()})")

    def delete(self, name: str) -> None:
        if not self.remove(self.target(name), self.TYPE_GENERIC, 0):
            error = self.ctypes.get_last_error()
            if error != self.ERROR_NOT_FOUND:
                raise KeychainError(f"the Credential Manager couldn't remove it (error {error})")


# -- macOS: the Keychain, through Security.framework


class _Mac:
    name = "macOS Keychain"
    NOT_FOUND = -25300  # errSecItemNotFound
    DUPLICATE = -25299  # errSecDuplicateItem
    UTF8 = 0x08000100  # kCFStringEncodingUTF8

    def __init__(self):
        import ctypes

        self.ctypes = ctypes
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        sec = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Security.framework/Security")
        void_p = ctypes.c_void_p
        cf.CFStringCreateWithCString.restype = void_p
        cf.CFStringCreateWithCString.argtypes = [void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFDataCreate.restype = void_p
        cf.CFDataCreate.argtypes = [void_p, ctypes.c_char_p, ctypes.c_long]
        cf.CFDataGetLength.restype = ctypes.c_long
        cf.CFDataGetLength.argtypes = [void_p]
        cf.CFDataGetBytePtr.restype = void_p
        cf.CFDataGetBytePtr.argtypes = [void_p]
        cf.CFDictionaryCreate.restype = void_p
        cf.CFDictionaryCreate.argtypes = [void_p, ctypes.POINTER(void_p), ctypes.POINTER(void_p), ctypes.c_long, void_p, void_p]
        cf.CFRelease.argtypes = [void_p]
        for fn in ("SecItemAdd", "SecItemCopyMatching"):
            getattr(sec, fn).restype = ctypes.c_int32
            getattr(sec, fn).argtypes = [void_p, ctypes.POINTER(void_p)]
        sec.SecItemUpdate.restype = ctypes.c_int32
        sec.SecItemUpdate.argtypes = [void_p, void_p]
        sec.SecItemDelete.restype = ctypes.c_int32
        sec.SecItemDelete.argtypes = [void_p]
        self.cf, self.sec = cf, sec

        def constant(lib, symbol: str) -> int:
            return ctypes.c_void_p.in_dll(lib, symbol).value

        self.k = {s: constant(sec, s) for s in ("kSecClass", "kSecClassGenericPassword", "kSecAttrService", "kSecAttrAccount",
                                                "kSecAttrLabel", "kSecValueData", "kSecReturnData", "kSecMatchLimit", "kSecMatchLimitOne")}
        self.k["kCFBooleanTrue"] = constant(cf, "kCFBooleanTrue")
        # The dictionaries' callbacks are structures, passed by address.
        self.key_callbacks = ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryKeyCallBacks"))
        self.value_callbacks = ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryValueCallBacks"))

    def _string(self, text: str) -> int:
        return self.cf.CFStringCreateWithCString(None, text.encode("utf-8"), self.UTF8)

    def _dict(self, pairs: list[tuple[int, int]]) -> int:
        void_p = self.ctypes.c_void_p
        keys = (void_p * len(pairs))(*[k for k, _ in pairs])
        values = (void_p * len(pairs))(*[v for _, v in pairs])
        return self.cf.CFDictionaryCreate(None, keys, values, len(pairs), self.key_callbacks, self.value_callbacks)

    def _query(self, name: str, *more: tuple[int, int]) -> tuple[int, list[int]]:
        """A query for this brain's entry, and what it holds that must be released after (the dictionary keeps its
        own references to them)."""
        service, account = self._string(SERVICE), self._string(name)
        made = [service, account]
        query = self._dict([(self.k["kSecClass"], self.k["kSecClassGenericPassword"]), (self.k["kSecAttrService"], service),
                            (self.k["kSecAttrAccount"], account), *more])
        return query, made

    def _release(self, *refs: int) -> None:
        for ref in refs:
            if ref:
                self.cf.CFRelease(ref)

    def get(self, name: str) -> str | None:
        ctypes = self.ctypes
        query, made = self._query(name, (self.k["kSecReturnData"], self.k["kCFBooleanTrue"]),
                                  (self.k["kSecMatchLimit"], self.k["kSecMatchLimitOne"]))
        result = ctypes.c_void_p()
        try:
            status = self.sec.SecItemCopyMatching(query, ctypes.byref(result))
        finally:
            self._release(query, *made)
        if status == self.NOT_FOUND:
            return None
        if status != 0:
            raise KeychainError(f"the Keychain couldn't be read (error {status})")
        try:
            length = self.cf.CFDataGetLength(result)
            data = ctypes.string_at(self.cf.CFDataGetBytePtr(result), length)
        finally:
            self._release(result.value)
        return data.decode("utf-8", "replace") or None

    def has(self, name: str) -> bool:
        query, made = self._query(name)  # nothing asked back: the entry's there or not, its key never read
        try:
            status = self.sec.SecItemCopyMatching(query, None)
        finally:
            self._release(query, *made)
        if status not in (0, self.NOT_FOUND):
            raise KeychainError(f"the Keychain couldn't be read (error {status})")
        return status == 0

    def set(self, name: str, secret: str) -> None:
        blob = secret.encode("utf-8")
        data = self.cf.CFDataCreate(None, blob, len(blob))
        label = self._string(f"Chatmon: the API key for {name}")
        try:
            query, made = self._query(name, (self.k["kSecValueData"], data), (self.k["kSecAttrLabel"], label))
            try:
                status = self.sec.SecItemAdd(query, None)
            finally:
                self._release(query, *made)
            if status == self.DUPLICATE:
                query, made = self._query(name)
                change = self._dict([(self.k["kSecValueData"], data)])
                try:
                    status = self.sec.SecItemUpdate(query, change)
                finally:
                    self._release(query, change, *made)
        finally:
            self._release(data, label)
        if status != 0:
            raise KeychainError(f"the Keychain couldn't save it (error {status})")

    def delete(self, name: str) -> None:
        query, made = self._query(name)
        try:
            status = self.sec.SecItemDelete(query)
        finally:
            self._release(query, *made)
        if status not in (0, self.NOT_FOUND):
            raise KeychainError(f"the Keychain couldn't remove it (error {status})")


# -- Linux and the BSDs: the Secret Service, over D-Bus


class _SecretService:
    """The freedesktop.org Secret Service API (https://specifications.freedesktop.org/secret-service/)."""

    name = "your desktop's keyring (Secret Service)"
    BUS = "org.freedesktop.secrets"
    ROOT = "/org/freedesktop/secrets"
    SERVICE_IFACE = "org.freedesktop.Secret.Service"
    ITEM_IFACE = "org.freedesktop.Secret.Item"
    TIMEOUT_MS = 5000  # a keyring that's starting, or stuck: never the 25 s D-Bus would otherwise wait

    def _call(self, path: str, interface: str, method: str, *args):
        from PyQt6.QtDBus import QDBus, QDBusConnection, QDBusMessage

        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            raise KeychainError("there's no desktop session bus to reach a keyring over")
        message = QDBusMessage.createMethodCall(self.BUS, path, interface, method)
        message.setArguments(list(args))
        reply = bus.call(message, QDBus.CallMode.Block, self.TIMEOUT_MS)
        if reply.type() != QDBusMessage.MessageType.ReplyMessage:
            if reply.errorName() == "org.freedesktop.DBus.Error.ServiceUnknown":
                raise KeychainError("no keyring is running (GNOME Keyring, KWallet or KeePassXC can be one)")
            raise KeychainError(f"the keyring said no ({reply.errorName() or 'no answer'})")
        return reply.arguments()

    @staticmethod
    def _attributes(name: str):
        from PyQt6.QtCore import QMetaType
        from PyQt6.QtDBus import QDBusArgument

        text = QMetaType(QMetaType.Type.QString.value)
        out = QDBusArgument()
        out.beginMap(text, text)  # a{ss}: a plain dict would go as a{sv}, which the service refuses
        for key, value in (("application", SERVICE), ("brain", name)):
            out.beginMapEntry()
            out.add(key)
            out.add(value)
            out.endMapEntry()
        out.endMap()
        return out

    @staticmethod
    def _paths(paths: list[str]):
        from PyQt6.QtCore import QMetaType
        from PyQt6.QtDBus import QDBusArgument, QDBusObjectPath

        out = QDBusArgument()
        out.beginArray(QMetaType.fromName(b"QDBusObjectPath"))  # ao, not av
        for path in paths:
            out.add(QDBusObjectPath(path))
        out.endArray()
        return out

    def _session(self) -> str:
        from PyQt6.QtDBus import QDBusVariant

        return str(self._call(self.ROOT, self.SERVICE_IFACE, "OpenSession", "plain", QDBusVariant(""))[1])

    def _close(self, session: str) -> None:
        try:
            self._call(session, "org.freedesktop.Secret.Session", "Close")
        except KeychainError:
            pass

    def _items(self, name: str) -> tuple[list[str], list[str]]:
        unlocked, locked = self._call(self.ROOT, self.SERVICE_IFACE, "SearchItems", self._attributes(name))
        return [str(p) for p in unlocked], [str(p) for p in locked]

    def get(self, name: str) -> str | None:
        unlocked, _locked = self._items(name)
        if not unlocked:
            return None  # none, or only in a locked keyring: never a prompt just to fill in the menu
        session = self._session()
        try:
            secret = self._call(unlocked[0], self.ITEM_IFACE, "GetSecret", self._object(session))[0]
        finally:
            self._close(session)
        return bytes(secret[2]).decode("utf-8", "replace") or None

    def has(self, name: str) -> bool:
        return bool(self._items(name)[0])  # in a keyring that's unlocked: one locked can't be read without asking

    def set(self, name: str, secret: str) -> None:
        from PyQt6.QtCore import QByteArray
        from PyQt6.QtDBus import QDBusArgument, QDBusVariant

        collection = str(self._call(self.ROOT, self.SERVICE_IFACE, "ReadAlias", "default")[0])
        if collection in ("", "/"):
            raise KeychainError("your keyring has no default collection to keep it in")
        self._unlock([collection])
        session = self._session()
        try:
            value = QDBusArgument()
            value.beginStructure()  # (oayays): session, parameters (none for "plain"), the secret, its type
            value.add(self._object(session))
            value.add(QByteArray(b""))
            value.add(QByteArray(secret.encode("utf-8")))
            value.add("text/plain; charset=utf8")
            value.endStructure()
            properties = {
                f"{self.ITEM_IFACE}.Label": QDBusVariant(f"Chatmon: the API key for {name}"),
                f"{self.ITEM_IFACE}.Attributes": QDBusVariant(self._attributes(name)),
            }
            _item, prompt = self._call(collection, "org.freedesktop.Secret.Collection", "CreateItem", properties, value, True)
        finally:
            self._close(session)
        if str(prompt) not in ("", "/"):
            self._prompt(str(prompt))
            raise KeychainError("your keyring asked to confirm: answer it, then save again")

    def delete(self, name: str) -> None:
        unlocked, locked = self._items(name)
        if locked:
            self._unlock(locked)
        for path in unlocked + locked:
            prompt = self._call(path, self.ITEM_IFACE, "Delete")[0]
            if str(prompt) not in ("", "/"):
                self._prompt(str(prompt))
                raise KeychainError("your keyring asked to confirm: answer it, then remove it again")

    def _unlock(self, paths: list[str]) -> None:
        _done, prompt = self._call(self.ROOT, self.SERVICE_IFACE, "Unlock", self._paths(paths))
        if str(prompt) not in ("", "/"):
            self._prompt(str(prompt))
            raise KeychainError("your keyring is locked: unlock it in the window it opened, then try again")

    def _prompt(self, path: str) -> None:
        """Show the keyring's own window (unlock, confirm) and leave it to you: nothing here waits for it."""
        try:
            self._call(path, "org.freedesktop.Secret.Prompt", "Prompt", "")
        except KeychainError:
            pass

    @staticmethod
    def _object(path: str):
        from PyQt6.QtDBus import QDBusObjectPath

        return QDBusObjectPath(path)
