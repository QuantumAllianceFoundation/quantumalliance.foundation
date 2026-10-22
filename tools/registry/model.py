"""Registry data model, loading, and validation (standard library only)."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Layer values in sort order; "no-signatures" ranks directly after "post-quantum".
LAYER_VALUES: tuple[str, ...] = (
    "post-quantum",
    "no-signatures",
    "post-quantum-ready",
    "quantum-aware",
    "quantum-vulnerable",
)
CATEGORY_LABELS: dict[str, str] = {
    "post-quantum": "Post-Quantum",
    "no-signatures": "No Signatures / Quantum Resistant",
    "post-quantum-ready": "Post-Quantum Ready",
    "quantum-aware": "Quantum-Aware",
    "quantum-vulnerable": "Quantum-Vulnerable",
}
FAMILIES = ("hash-based", "lattice", "other")
SAFETY_BY_FAMILY = {"hash-based": "High", "lattice": "Medium", "other": "Low"}
SAFETY_RANK = {"High": 0, "Medium": 1, "Low": 2}
MAX_LINKS = 2
MAX_NOTE_WORDS = 5
MAX_SUMMARY_WORDS = 80
MAX_PAPERS = 3
MAX_LOGO_BYTES = 65536
LOGO_EXTENSIONS = (".svg", ".png", ".webp")
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
    summary: str
    papers: tuple[Link, ...]


@dataclass(frozen=True)
class Size:
    bytes: int
    parameter_set: str


@dataclass(frozen=True)
class Chain:
    name: str
    consensus: str
    transactions: str
    website: str
    source: str
    algorithms: tuple[str, ...]
    note: str | None
    links: tuple[Link, ...]
    logo: str | None = None


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
    note: str | None
    links: tuple[Link, ...]


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


def _transactions(value: Any) -> str:
    if value == "no-signatures":
        raise ValueError("no-signatures is allowed for consensus only")
    return _choice(tuple(v for v in LAYER_VALUES if v != "no-signatures"))(value)


def _note(value: Any) -> str:
    text = _text(value)
    words = len(text.split())
    if words > MAX_NOTE_WORDS:
        raise ValueError(f"must be at most {MAX_NOTE_WORDS} words (got {words})")
    return text


def _summary(value: Any) -> str:
    text = _text(value)
    words = len(text.split())
    if words > MAX_SUMMARY_WORDS:
        raise ValueError(f"must be at most {MAX_SUMMARY_WORDS} words (got {words})")
    return text


_SCRIPT = re.compile(r"<script", re.IGNORECASE)
_EVENT_ATTRIBUTE = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


def _logo(logos_dir: Path) -> Callable[[Any], str]:
    def check(value: Any) -> str:
        name = _text(value)
        if name != Path(name).name:
            raise ValueError(f"must be a file name without a directory (got {name!r})")
        if Path(name).suffix.lower() not in LOGO_EXTENSIONS:
            raise ValueError(f"must end in .svg, .png, or .webp (got {name!r})")
        try:
            data = (logos_dir / name).read_bytes()
        except OSError as exc:
            raise ValueError(
                f"cannot read {name} in {logos_dir}: {exc.strerror or exc}"
            ) from exc
        if len(data) > MAX_LOGO_BYTES:
            raise ValueError(
                f"{name} must be at most {MAX_LOGO_BYTES} bytes (got {len(data)})"
            )
        if name.lower().endswith(".svg"):
            text = data.decode("utf-8", errors="replace")
            if _SCRIPT.search(text) or _EVENT_ATTRIBUTE.search(text):
                raise ValueError(f"{name} must not contain <script> or on* attributes")
        return name

    return check


def _flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("must be true or false")
    return value


def _list_of(
    item: Callable[[Any], Any], *, non_empty: bool = False, max_items: int | None = None
) -> Callable[[Any], tuple]:
    def check(value: Any) -> tuple:
        if not isinstance(value, list):
            raise ValueError("must be a list")
        if non_empty and not value:
            raise ValueError("must not be empty")
        if max_items is not None and len(value) > max_items:
            raise ValueError(f"must have at most {max_items} entries (got {len(value)})")
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
            "summary": (_summary, _REQUIRED),
            "papers": (_list_of(_link, non_empty=True, max_items=MAX_PAPERS), _REQUIRED),
        },
        "id",
    ),
    "blockchains": (
        "chain",
        Chain,
        {
            "name": (_text, _REQUIRED),
            "consensus": (_choice(LAYER_VALUES), _REQUIRED),
            "transactions": (_transactions, _REQUIRED),
            "website": (_url, _REQUIRED),
            "source": (_url, _REQUIRED),
            "algorithms": (_list_of(_text), ()),
            "note": (_note, None),
            "links": (_list_of(_link, max_items=MAX_LINKS), ()),
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
            "note": (_note, None),
            "links": (_list_of(_link, max_items=MAX_LINKS), ()),
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
    kind: str,
    fields: dict[str, tuple[Callable[[Any], Any], Any]],
    raw: Any,
    index: int,
    filename: str,
    errors: list[str],
) -> Any | None:
    """Validate one entry; append errors and return None if it is invalid."""
    _, cls, _, name_key = _SPECS[kind]
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


def _load_kind(
    data_dir: Path, logos_dir: Path, kind: str, errors: list[str]
) -> list[Any]:
    filename = f"{kind}.toml"
    array, _, spec_fields, name_key = _SPECS[kind]
    fields = dict(spec_fields)
    if kind == "blockchains":
        fields["logo"] = (_logo(logos_dir), None)
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
        entry = _build_entry(kind, fields, raw, index, filename, errors)
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


def load_registry(data_dir: Path, logos_dir: Path | None = None) -> Registry:
    """Load and validate the four registry files, raising one RegistryError.

    Chain logos are read from logos_dir, which defaults to
    assets/registry/logos next to the registry directory.
    """
    if logos_dir is None:
        logos_dir = data_dir.parent.parent / "assets" / "registry" / "logos"
    errors: list[str] = []
    algorithms = _load_kind(data_dir, logos_dir, "algorithms", errors)
    chains = _load_kind(data_dir, logos_dir, "blockchains", errors)
    libraries = _load_kind(data_dir, logos_dir, "libraries", errors)
    products = _load_kind(data_dir, logos_dir, "products", errors)
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


def library_slug(name: str) -> str:
    """Return the anchor slug for a library name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
