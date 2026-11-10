{ Putting Chatmon's folder on PATH and taking it off again, exactly: the value keeps its registry type
  (REG_SZ or REG_EXPAND_SZ) and every other entry as it was, separators and all. Included by chatmon.iss. }

const
  REG_SZ = 1;
  REG_EXPAND_SZ = 2;
  RRF_RT_ANY = $0000FFFF;
  RRF_NOEXPAND = $10000000;

function RegGetValueW(Key: Integer; SubKey, Name: String; Flags: Cardinal; var Kind: Cardinal; Data: Integer; Size: Integer): Integer;
  external 'RegGetValueW@advapi32.dll stdcall';

{ Inno's HKLM or HKCU, as the handle Windows itself knows. }
function NativeRoot(Root: Integer): Integer;
begin
  if Root = HKLM then Result := $80000002 else Result := $80000001;
end;

{ The value's type as it is now: REG_SZ, or REG_EXPAND_SZ (also when there's no value yet). }
function PathKind(Root: Integer; Key, Name: String): Cardinal;
var
  Kind: Cardinal;
begin
  Kind := 0;
  if (RegGetValueW(NativeRoot(Root), Key, Name, RRF_RT_ANY or RRF_NOEXPAND, Kind, 0, 0) = 0) and (Kind = REG_SZ) then
    Result := REG_SZ
  else
    Result := REG_EXPAND_SZ;
end;

{ Where Dir is in Paths (1-based, in ';' + Paths + ';'), or 0. }
function FindInPath(Paths, Dir: String): Integer;
begin
  Result := Pos(';' + Uppercase(RemoveBackslashUnlessRoot(Dir)) + ';', ';' + Uppercase(Paths) + ';');
end;

{ Paths with Dir on the end, in the separators' own style: "a;b" gives "a;b;Dir", "a;b;" gives "a;b;Dir;". }
function WithDir(Paths, Dir: String): String;
begin
  if Paths = '' then
    Result := Dir
  else if Copy(Paths, Length(Paths), 1) = ';' then
    Result := Paths + Dir + ';'
  else
    Result := Paths + ';' + Dir;
end;

{ Paths without Dir: it goes with the separator after it, which undoes WithDir exactly. }
function WithoutDir(Paths, Dir: String): String;
var
  Padded: String;
  At: Integer;
begin
  Result := Paths;
  At := FindInPath(Paths, Dir);
  if At = 0 then exit;
  Padded := ';' + Paths + ';';
  Delete(Padded, At + 1, Length(RemoveBackslashUnlessRoot(Dir)) + 1);
  Result := Copy(Padded, 2, Length(Padded) - 2);
end;

procedure WritePath(Root: Integer; Key, Name, Paths: String; Kind: Cardinal);
begin
  if Kind = REG_SZ then
    RegWriteStringValue(Root, Key, Name, Paths)
  else
    RegWriteExpandStringValue(Root, Key, Name, Paths);
end;

procedure AddToPath(Root: Integer; Key, Dir: String);
var
  Paths: String;
begin
  if not RegQueryStringValue(Root, Key, 'Path', Paths) then Paths := '';
  if FindInPath(Paths, Dir) > 0 then exit;
  WritePath(Root, Key, 'Path', WithDir(Paths, Dir), PathKind(Root, Key, 'Path'));
end;

procedure RemoveFromPath(Root: Integer; Key, Dir: String);
var
  Paths, Left: String;
begin
  if not RegQueryStringValue(Root, Key, 'Path', Paths) then exit;
  Left := WithoutDir(Paths, Dir);
  if Left = Paths then exit;
  if Left = '' then
    RegDeleteValue(Root, Key, 'Path')  { it was only ever there for Chatmon }
  else
    WritePath(Root, Key, 'Path', Left, PathKind(Root, Key, 'Path'));
end;
