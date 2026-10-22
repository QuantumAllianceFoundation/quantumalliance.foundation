"""Registry data model, loading, and validation (standard library only)."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATEGORIES: tuple[str, ...] = (
    "post-quantum",
    "post-quantum-ready",
    "quantum-aware",
    "quantum-vulnerable",
)
CATEGORY_LABELS: dict[str, str] = {
    "post-quantum": "Post-Quantum",
    "post-quantum-ready": "Post-Quantum Ready",
    "quantum-aware": "Quantum-Aware",
    "quantum-vulnerable": "Quantum-Vulnerable",
}
FAMILIES = ("hash-based", "lattice", "other")
SAFETY_BY_FAMILY = {"hash-based": "High", "lattice": "Medium", "other": "Low"}
SAFETY_RANK = {"High": 0, "Medium": 1, "Low": 2}
MATURITIES = ("experimental", "pre-production", "production")


@dataclass(frozen=True)
class Link:
    title: str
    url: str


@dataclass(frozen=True)
class Algorithm:
    id: str
    name: str
    family: str
    url: str


@dataclass(frozen=True)
class Size:
    bytes: int
    parameter_set: str


@dataclass(frozen=True)
class Chain:
    name: str
    category: str
    website: str
    source: str
    algorithms: tuple[str, ...]
    notes: tuple[Link, ...]


@dataclass(frozen=True)
class Library:
    name: str
    source: str
    algorithms: tuple[str, ...]
    maturity: str
    blockchain_friendly: bool
    audits: tuple[Link, ...]
    min_signature: Size | None
    min_public_key: Size | None
    notes: tuple[str, ...]


@dataclass(frozen=True)
class Product:
    name: str
    member: str
    description: str
    chains: tuple[str, ...]
    url: str


@dataclass(frozen=True)
class Registry:
    algorithms: dict[str, Algorithm]
    chains: tuple[Chain, ...]
    libraries: tuple[Library, ...]
    products: tuple[Product, ...]


class RegistryError(Exception):
    """Raised once, carrying every validation error found."""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


class _Problem(Exception):
    """A single field problem inside one entry."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


# Field validators. Each takes the raw value and returns the converted value,
# or raises ValueError with a message.


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-empty string")
    return value


_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _slug(value: Any) -> str:
    text = _text(value)
    if not _SLUG.fullmatch(text):
        raise ValueError(
            f"must be a lowercase slug such as ml-dsa (got {text!r})"
        )
    return text


def _url(value: Any) -> str:
    text = _text(value)
    if not text.startswith("https://"):
        raise ValueError(f"must start with https:// (got {text!r})")
    return text


def _choice(options: tuple[str, ...]) -> Callable[[Any], str]:
    def check(value: Any) -> str:
        if value not in options:
            raise ValueError(f"must be one of {', '.join(options)} (got {value!r})")
        return value

    return check


def _flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("must be true or false")
    return value


def _list_of(item: Callable[[Any], Any], *, non_empty: bool = False) -> Callable[[Any], tuple]:
    def check(value: Any) -> tuple:
        if not isinstance(value, list):
            raise ValueError("must be a list")
        if non_empty and not value:
            raise ValueError("must not be empty")
        return tuple(item(v) for v in value)

    return check


def _table(
    build: Callable[..., Any], **fields: Callable[[Any], Any]
) -> Callable[[Any], Any]:
    def check(value: Any) -> Any:
        if not isinstance(value, dict):
            raise ValueError("must be a table")
        extra = sorted(set(value) - set(fields))
        if extra:
            raise ValueError(f"unknown key(s): {', '.join(extra)}")
        missing = [k for k in fields if k not in value]
        if missing:
            raise ValueError(f"missing key(s): {', '.join(missing)}")
        return build(**{k: fields[k](value[k]) for k in fields})

    return check


def _positive_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("must be a positive integer")
    return value


_link = _table(Link, title=_text, url=_url)
_size = _table(Size, bytes=_positive_int, parameter_set=_text)

_REQUIRED = object()

# kind -> (TOML array name, dataclass, {field: (validator, default or _REQUIRED)}, name key)
_SPECS: dict[str, tuple[str, type, dict[str, tuple[Callable[[Any], Any], Any]], str]] = {
    "algorithms": (
        "algorithm",
        Algorithm,
        {
            "id": (_slug, _REQUIRED),
            "name": (_text, _REQUIRED),
            "family": (_choice(FAMILIES), _REQUIRED),
            "url": (_url, _REQUIRED),
        },
        "id",
    ),
    "blockchains": (
        "chain",
        Chain,
        {
            "name": (_text, _REQUIRED),
            "category": (_choice(CATEGORIES), _REQUIRED),
            "website": (_url, _REQUIRED),
            "source": (_url, _REQUIRED),
            "algorithms": (_list_of(_text), ()),
            "notes": (_list_of(_link), ()),
        },
        "name",
    ),
    "libraries": (
        "library",
        Library,
        {
            "name": (_text, _REQUIRED),
            "source": (_url, _REQUIRED),
            "algorithms": (_list_of(_text, non_empty=True), _REQUIRED),
            "maturity": (_choice(MATURITIES), _REQUIRED),
            "blockchain_friendly": (_flag, _REQUIRED),
            "audits": (_list_of(_link), ()),
            "min_signature": (_size, None),
            "min_public_key": (_size, None),
            "notes": (_list_of(_text), ()),
        },
        "name",
    ),
    "products": (
        "product",
        Product,
        {
            "name": (_text, _REQUIRED),
            "member": (_text, _REQUIRED),
            "description": (_text, _REQUIRED),
            "chains": (_list_of(_text, non_empty=True), _REQUIRED),
            "url": (_url, _REQUIRED),
        },
        "name",
    ),
}


def _build_entry(
    kind: str, raw: Any, index: int, filename: str, errors: list[str]
) -> Any | None:
    """Validate one entry; append errors and return None if it is invalid."""
    _, cls, fields, name_key = _SPECS[kind]
    if not isinstance(raw, dict):
        errors.append(f"{filename}: #{index}: entry: must be a table")
        return None
    name = raw.get(name_key)
    label = name if isinstance(name, str) and name.strip() else f"#{index}"
    problems: list[_Problem] = []
    for key in sorted(set(raw) - set(fields)):
        problems.append(_Problem(key, "unknown key"))
    values: dict[str, Any] = {}
    for key, (check, default) in fields.items():
        if key not in raw:
            if default is _REQUIRED:
                problems.append(_Problem(key, "required"))
            else:
                values[key] = default
            continue
        try:
            values[key] = check(raw[key])
        except ValueError as exc:
            problems.append(_Problem(key, str(exc)))
    errors.extend(f"{filename}: {label}: {p.field}: {p.message}" for p in problems)
    return None if problems else cls(**values)


def _load_kind(data_dir: Path, kind: str, errors: list[str]) -> list[Any]:
    filename = f"{kind}.toml"
    array, _, _, name_key = _SPECS[kind]
    try:
        text = (data_dir / filename).read_text(encoding="utf-8-sig")
        doc = tomllib.loads(text)
    except OSError as exc:
        errors.append(f"{filename}: file: {exc.strerror or exc}")
        return []
    except UnicodeDecodeError as exc:
        errors.append(
            f"{filename}: file: not valid UTF-8 (byte {exc.start}); save the file as UTF-8"
        )
        return []
    except tomllib.TOMLDecodeError as exc:
        errors.append(f"{filename}: toml: {exc}")
        return []
    for key in sorted(set(doc) - {array}):
        errors.append(f"{filename}: top level: {key}: unknown key (expected [[{array}]])")
    raw_entries = doc.get(array, [])
    if not isinstance(raw_entries, list):
        errors.append(f"{filename}: top level: {array}: must be an array of tables")
        return []
    entries = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries, start=1):
        entry = _build_entry(kind, raw, index, filename, errors)
        if entry is None:
            continue
        name = getattr(entry, name_key)
        if name.casefold() in seen:
            errors.append(f"{filename}: {name}: {name_key}: duplicate (names compare case-insensitively)")
            continue
        seen.add(name.casefold())
        entries.append(entry)
    return entries


def _check_algorithm_refs(
    filename: str,
    items: list[Any],
    algorithms: Mapping[str, Algorithm],
    errors: list[str],
) -> None:
    for item in items:
        unknown = [a for a in item.algorithms if a not in algorithms]
        if unknown:
            errors.append(
                f"{filename}: {item.name}: algorithms: unknown id(s): {', '.join(unknown)}"
            )


def load_registry(data_dir: Path) -> Registry:
    """Load and validate the four registry files, raising one RegistryError."""
    errors: list[str] = []
    algorithms = _load_kind(data_dir, "algorithms", errors)
    chains = _load_kind(data_dir, "blockchains", errors)
    libraries = _load_kind(data_dir, "libraries", errors)
    products = _load_kind(data_dir, "products", errors)
    catalog = {a.id: a for a in algorithms}
    _check_algorithm_refs("blockchains.toml", chains, catalog, errors)
    _check_algorithm_refs("libraries.toml", libraries, catalog, errors)
    if errors:
        raise RegistryError(errors)
    return Registry(catalog, tuple(chains), tuple(libraries), tuple(products))


def library_safety(lib: Library, algorithms: Mapping[str, Algorithm]) -> str:
    """Return the highest safety rating among the library's algorithms."""
    ratings = [SAFETY_BY_FAMILY[algorithms[a].family] for a in lib.algorithms]
    return min(ratings, key=SAFETY_RANK.__getitem__)
