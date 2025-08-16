In CocoIndex, a KTable maps to dict[K, V] where V must be a Struct (dataclass or NamedTuple). So dict[str, Dep] is valid as long as Dep is a Struct, not a primitive. This is exactly what the CocoIndex docs say under Data Types → KTable and Struct Types. 
cocoindex.io

Why your error happened
The exception KTable value must be a Struct type, got <class 'int'> is what you’d get if a field in your row Struct is a dict of primitives (e.g., dict[str, int]). Any dict[...] inside a Struct is interpreted as a nested KTable, and per the spec, its value-type must be a Struct (not int, str, …). 
cocoindex.io

Two perfectly valid fixes (both spec-compliant)

Keep your deps as a nested KTable with a Struct value
Define a small dataclass and change the annotation:

from dataclasses import dataclass

@dataclass
class Dep:
    count: int  # you can add kind/lang/etc later

@dataclass(frozen=True)
class Chunk:
    ...
    deps: dict[str, Dep]  # KTable: key=str, value=Struct


When building deps:

dep_counts: dict[str, int] = ...
deps_struct = {name: Dep(count=int(c)) for name, c in dep_counts.items()}


Now the nested dict[...] satisfies “V is a Struct”. (Docs: KTable dict[K, V]; V must be a Struct. Structs are dataclasses/NamedTuples.) 
cocoindex.io

Or avoid a nested KTable entirely
Represent dependencies as a list of Structs (an LTable), e.g.:

@dataclass
class Dep:
    name: str
    count: int

@dataclass(frozen=True)
class Chunk:
    ...
    deps: list[Dep]  # LTable: list of Struct


This also aligns with the spec (LTable is list[R] where R is a Struct). It’s simpler if you don’t need key-based lookups/joins on deps. 
cocoindex.io

A note on your row() usage
Your switch to with data_scope["files"].row() as f: is also per the book—row() is how CocoIndex expects you to attach per-row transforms so the table value remains a Struct. The flow-definition guide shows this exact pattern. 
cocoindex.io

When to choose which:

Use dict[str, Dep] if you’ll do key-based joins/merges/dedup by identifier name later (natural KTable semantics).

Use list[Dep] if it’s just metadata you iterate over—lighter and avoids accidental KTable rules.

Either way, the key rule is: no dict[str, int] (or other primitive) inside a row Struct—make the value a Struct.

If you’d like, I can draft a tiny patch that swaps deps: Dict[str, int] → deps: Dict[str, Dep] (or List[Dep]) and updates the construction code accordingly.What’s breaking (and why)

The error:

ValueError: KTable value must have a Struct type, got <class 'int'>


is triggered because we declared the deps field on our chunk as a Dict[str, int]. In CocoIndex’s type system, a dict[K, V] is treated as a KTable; the V (the table row value) must be a Struct, not a primitive like int. So Dict[str, int] is illegal in a KTable context and produces exactly this error. The official docs call this out: KTable value types must be Structs; dict[K,V] is encoded as a KTable where V must be a struct, while lists of Struct are modeled as an LTable and are fine. 
cocoindex.io

We already fixed .row() usage (only call it once per table slice), which matches CocoIndex’s “for-each-row” pattern. This new error is independent of that and is purely about the field type. 
cocoindex.io

Minimal, safe fix

Change deps from Dict[str, int] → List[Dep], where Dep is a tiny dataclass:

This makes deps an LTable of Struct, which CocoIndex supports natively.

We’ll still keep the same information: each dependency’s name and count.

Also, update the PageRank loader to handle both the new List[Dep] and (for safety) any legacy rows that might still be dict.


