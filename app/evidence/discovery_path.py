"""
Investigation provenance and discovery paths.

Represents how investigation objects were discovered
or derived from other investigation objects.

Responsibilities:

- represent universal discovery nodes
- represent directed discovery edges
- preserve discovery method, relation, tool and reason
- build explainable root -> target paths
- support multiple roots and multiple parents
- prevent cross-case provenance
- prevent self-loops
- prevent provenance cycles
- deduplicate equivalent discovery edges
- keep discovery provenance separate from confidence

Does NOT:

- calculate Evidence Confidence
- calculate Entity Resolution confidence
- calculate Entity <-> Evidence association score
- execute OSINT connectors
- perform pivots automatically
- access the database
"""

from __future__ import annotations

from collections import deque

from dataclasses import (
    dataclass,
    field,
)

from enum import Enum

from typing import Any

from uuid import UUID


# ==========================================================
# Object type
# ==========================================================


class DiscoveryObjectType(
    str,
    Enum,
):
    """
    Supported investigation objects that may appear
    inside a discovery path.
    """

    SOURCE = "source"

    EVIDENCE = "evidence"

    ENTITY = "entity"

    OSINT_FINDING = "osint_finding"

    SEARCH_RESULT = "search_result"

    DOCUMENT = "document"

    MESSAGE = "message"

    RELATIONSHIP = "relationship"

    ARTIFACT = "artifact"

    OTHER = "other"


# ==========================================================
# Discovery method
# ==========================================================


class DiscoveryMethod(
    str,
    Enum,
):
    """
    Method that produced a child object.

    Method describes HOW discovery happened.

    It is deliberately separate from confidence,
    reliability and score.
    """

    IMPORT = "import"

    EXTRACTION = "extraction"

    ENTITY_ASSOCIATION = "entity_association"

    ENTITY_RESOLUTION = "entity_resolution"

    OSINT = "osint"

    SEARCH = "search"

    MANUAL = "manual"

    DERIVATION = "derivation"

    ANALYSIS = "analysis"


# ==========================================================
# Discovery node
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryNode:
    """
    One object inside a discovery graph.

    object_id is stored as text intentionally.

    Persistent objects may use UUID strings, while
    transient objects such as OSINT findings or search
    results may use stable non-UUID identifiers.
    """

    case_id: UUID

    object_type: DiscoveryObjectType

    object_id: str

    label: str = ""

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.object_type,
            DiscoveryObjectType,
        ):

            raise TypeError(
                "object_type must be a "
                "DiscoveryObjectType."
            )

        if not isinstance(
            self.object_id,
            str,
        ):

            raise TypeError(
                "object_id must be a string."
            )

        normalized_id = (
            self.object_id.strip()
        )

        if not normalized_id:

            raise ValueError(
                "object_id cannot be empty."
            )

        object.__setattr__(
            self,
            "object_id",
            normalized_id,
        )

        if not isinstance(
            self.label,
            str,
        ):

            raise TypeError(
                "label must be a string."
            )

        object.__setattr__(
            self,
            "label",
            self.label.strip(),
        )

        if not isinstance(
            self.metadata,
            dict,
        ):

            raise TypeError(
                "metadata must be a dictionary."
            )

        object.__setattr__(
            self,
            "metadata",
            dict(
                self.metadata
            ),
        )

    @property
    def key(
        self,
    ) -> tuple[
        DiscoveryObjectType,
        str,
    ]:

        return (
            self.object_type,
            self.object_id,
        )

    @property
    def display_label(
        self,
    ) -> str:

        if self.label:

            return self.label

        return (
            f"{self.object_type.value}:"
            f"{self.object_id}"
        )


# ==========================================================
# Discovery edge
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryEdge:
    """
    Directed provenance relation:

        parent
          ↓
        child

    Example:

        Telegram message
            -- extraction / username -->
        @example Entity
    """

    case_id: UUID

    parent_type: DiscoveryObjectType

    parent_id: str

    child_type: DiscoveryObjectType

    child_id: str

    method: DiscoveryMethod

    relation: str

    tool: str | None = None

    reason: str = ""

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not isinstance(
            self.parent_type,
            DiscoveryObjectType,
        ):

            raise TypeError(
                "parent_type must be a "
                "DiscoveryObjectType."
            )

        if not isinstance(
            self.child_type,
            DiscoveryObjectType,
        ):

            raise TypeError(
                "child_type must be a "
                "DiscoveryObjectType."
            )

        parent_id = str(
            self.parent_id
        ).strip()

        child_id = str(
            self.child_id
        ).strip()

        if not parent_id:

            raise ValueError(
                "parent_id cannot be empty."
            )

        if not child_id:

            raise ValueError(
                "child_id cannot be empty."
            )

        object.__setattr__(
            self,
            "parent_id",
            parent_id,
        )

        object.__setattr__(
            self,
            "child_id",
            child_id,
        )

        if (
            self.parent_key
            ==
            self.child_key
        ):

            raise ValueError(
                "Discovery edge cannot "
                "create a self-loop."
            )

        if not isinstance(
            self.method,
            DiscoveryMethod,
        ):

            raise TypeError(
                "method must be a "
                "DiscoveryMethod."
            )

        if not isinstance(
            self.relation,
            str,
        ):

            raise TypeError(
                "relation must be a string."
            )

        relation = (
            self.relation.strip()
        )

        if not relation:

            raise ValueError(
                "relation cannot be empty."
            )

        object.__setattr__(
            self,
            "relation",
            relation,
        )

        if self.tool is not None:

            if not isinstance(
                self.tool,
                str,
            ):

                raise TypeError(
                    "tool must be a string "
                    "or None."
                )

            tool = (
                self.tool.strip()
            )

            if not tool:

                raise ValueError(
                    "tool cannot be empty."
                )

            object.__setattr__(
                self,
                "tool",
                tool,
            )

        if not isinstance(
            self.reason,
            str,
        ):

            raise TypeError(
                "reason must be a string."
            )

        object.__setattr__(
            self,
            "reason",
            self.reason.strip(),
        )

        if not isinstance(
            self.metadata,
            dict,
        ):

            raise TypeError(
                "metadata must be a dictionary."
            )

        object.__setattr__(
            self,
            "metadata",
            dict(
                self.metadata
            ),
        )

    @property
    def parent_key(
        self,
    ) -> tuple[
        DiscoveryObjectType,
        str,
    ]:

        return (
            self.parent_type,
            self.parent_id,
        )

    @property
    def child_key(
        self,
    ) -> tuple[
        DiscoveryObjectType,
        str,
    ]:

        return (
            self.child_type,
            self.child_id,
        )

    @property
    def identity_key(
        self,
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
        str,
        str,
    ]:
        """
        Semantic edge identity used for deduplication.

        Reason and metadata do not create a second
        discovery relation when the structural relation
        is already identical.
        """

        return (
            self.parent_type.value,
            self.parent_id,
            self.child_type.value,
            self.child_id,
            self.method.value,
            self.relation,
            self.tool
            or "",
        )

    @classmethod
    def from_nodes(
        cls,
        *,
        parent: DiscoveryNode,
        child: DiscoveryNode,
        method: DiscoveryMethod,
        relation: str,
        tool: str | None = None,
        reason: str = "",
        metadata: dict[
            str,
            Any,
        ] | None = None,
    ) -> "DiscoveryEdge":
        """
        Create an edge from two discovery nodes.
        """

        if (
            parent.case_id
            !=
            child.case_id
        ):

            raise ValueError(
                "Cross-case discovery edge "
                "is not allowed."
            )

        return cls(
            case_id=parent.case_id,
            parent_type=(
                parent.object_type
            ),
            parent_id=(
                parent.object_id
            ),
            child_type=(
                child.object_type
            ),
            child_id=(
                child.object_id
            ),
            method=method,
            relation=relation,
            tool=tool,
            reason=reason,
            metadata=dict(
                metadata
                or {}
            ),
        )


# ==========================================================
# Discovery path
# ==========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryPath:
    """
    One complete root -> target discovery chain.

    Path is structural provenance only.

    It deliberately contains no confidence score.
    """

    case_id: UUID

    nodes: tuple[
        DiscoveryNode,
        ...,
    ]

    edges: tuple[
        DiscoveryEdge,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:

        if not isinstance(
            self.case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        if not self.nodes:

            raise ValueError(
                "DiscoveryPath requires "
                "at least one node."
            )

        if (
            len(
                self.edges
            )
            !=
            len(
                self.nodes
            )
            -
            1
        ):

            raise ValueError(
                "DiscoveryPath node/edge "
                "counts are inconsistent."
            )

        for node in self.nodes:

            if (
                node.case_id
                !=
                self.case_id
            ):

                raise ValueError(
                    "Cross-case node found "
                    "inside DiscoveryPath."
                )

        for index, edge in enumerate(
            self.edges
        ):

            if (
                edge.case_id
                !=
                self.case_id
            ):

                raise ValueError(
                    "Cross-case edge found "
                    "inside DiscoveryPath."
                )

            if (
                self.nodes[
                    index
                ].key
                !=
                edge.parent_key
            ):

                raise ValueError(
                    "DiscoveryPath edge parent "
                    "does not match path nodes."
                )

            if (
                self.nodes[
                    index
                    +
                    1
                ].key
                !=
                edge.child_key
            ):

                raise ValueError(
                    "DiscoveryPath edge child "
                    "does not match path nodes."
                )

    @property
    def root(
        self,
    ) -> DiscoveryNode:

        return self.nodes[
            0
        ]

    @property
    def target(
        self,
    ) -> DiscoveryNode:

        return self.nodes[
            -1
        ]

    @property
    def depth(
        self,
    ) -> int:

        return len(
            self.edges
        )

    @property
    def tools_used(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        """
        Unique tools in path order.
        """

        result: list[
            str
        ] = []

        seen: set[
            str
        ] = set()

        for edge in self.edges:

            if (
                edge.tool
                and
                edge.tool
                not in seen
            ):

                seen.add(
                    edge.tool
                )

                result.append(
                    edge.tool
                )

        return tuple(
            result
        )

    @property
    def methods_used(
        self,
    ) -> tuple[
        DiscoveryMethod,
        ...,
    ]:
        """
        Unique discovery methods in path order.
        """

        result: list[
            DiscoveryMethod
        ] = []

        seen: set[
            DiscoveryMethod
        ] = set()

        for edge in self.edges:

            if edge.method in seen:

                continue

            seen.add(
                edge.method
            )

            result.append(
                edge.method
            )

        return tuple(
            result
        )

    @property
    def explainable_chain(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        """
        Human-readable discovery chain.
        """

        lines: list[
            str
        ] = []

        for index, edge in enumerate(
            self.edges
        ):

            parent = (
                self.nodes[
                    index
                ]
            )

            child = (
                self.nodes[
                    index
                    +
                    1
                ]
            )

            method_text = (
                edge.method.value
            )

            if edge.tool:

                method_text = (
                    f"{method_text}"
                    f" via {edge.tool}"
                )

            line = (
                f"{parent.display_label} "
                f"--[{method_text}; "
                f"{edge.relation}]--> "
                f"{child.display_label}"
            )

            if edge.reason:

                line += (
                    f" ({edge.reason})"
                )

            lines.append(
                line
            )

        return tuple(
            lines
        )


# ==========================================================
# Discovery graph / service
# ==========================================================


class DiscoveryPathService:
    """
    In-memory provenance DAG.

    A node becomes a discovery root only through
    register_root().

    Therefore an arbitrary disconnected node is NOT
    automatically treated as a valid discovery path.
    """

    def __init__(
        self,
        case_id: UUID,
    ) -> None:

        if not isinstance(
            case_id,
            UUID,
        ):

            raise TypeError(
                "case_id must be UUID."
            )

        self.case_id = (
            case_id
        )

        self._nodes: dict[
            tuple[
                DiscoveryObjectType,
                str,
            ],
            DiscoveryNode,
        ] = {}

        self._edges: list[
            DiscoveryEdge
        ] = []

        self._edge_keys: set[
            tuple[
                str,
                str,
                str,
                str,
                str,
                str,
                str,
            ]
        ] = set()

        self._root_keys: set[
            tuple[
                DiscoveryObjectType,
                str,
            ]
        ] = set()

    # ==========================================================
    # Nodes
    # ==========================================================

    def add_node(
        self,
        node: DiscoveryNode,
    ) -> bool:
        """
        Add a discovery node.

        Returns True when newly added.

        Conflicting duplicate definitions are rejected.
        """

        self._validate_node_case(
            node
        )

        existing = self._nodes.get(
            node.key
        )

        if existing is None:

            self._nodes[
                node.key
            ] = node

            return True

        if existing != node:

            raise ValueError(
                "Conflicting DiscoveryNode "
                "definition for the same object."
            )

        return False

    def register_root(
        self,
        node: DiscoveryNode,
    ) -> bool:
        """
        Register an explicit discovery root.

        Roots may represent:

        - imported Source
        - manually entered Entity
        - initial investigation target
        - other starting object
        """

        self.add_node(
            node
        )

        if node.key in self._root_keys:

            return False

        self._root_keys.add(
            node.key
        )

        return True

    def get_node(
        self,
        object_type: DiscoveryObjectType,
        object_id: str,
    ) -> DiscoveryNode | None:

        key = self._make_key(
            object_type,
            object_id,
        )

        return self._nodes.get(
            key
        )

    # ==========================================================
    # Edges
    # ==========================================================

    def add_edge(
        self,
        edge: DiscoveryEdge,
    ) -> bool:
        """
        Add a directed discovery edge.

        Returns False for an equivalent duplicate edge.

        Raises when the edge would create a cycle.
        """

        if not isinstance(
            edge,
            DiscoveryEdge,
        ):

            raise TypeError(
                "edge must be a DiscoveryEdge."
            )

        if (
            edge.case_id
            !=
            self.case_id
        ):

            raise ValueError(
                "Cross-case discovery edge "
                "is not allowed."
            )

        if (
            edge.parent_key
            not in
            self._nodes
        ):

            raise LookupError(
                "Discovery edge parent node "
                "is not registered."
            )

        if (
            edge.child_key
            not in
            self._nodes
        ):

            raise LookupError(
                "Discovery edge child node "
                "is not registered."
            )

        if (
            edge.identity_key
            in
            self._edge_keys
        ):

            return False

        # Adding parent -> child creates a cycle when
        # child can already reach parent.
        if self._path_exists(
            start=edge.child_key,
            target=edge.parent_key,
        ):

            raise ValueError(
                "Discovery edge would create "
                "a provenance cycle."
            )

        self._edges.append(
            edge
        )

        self._edge_keys.add(
            edge.identity_key
        )

        return True

    def connect(
        self,
        *,
        parent: DiscoveryNode,
        child: DiscoveryNode,
        method: DiscoveryMethod,
        relation: str,
        tool: str | None = None,
        reason: str = "",
        metadata: dict[
            str,
            Any,
        ] | None = None,
    ) -> bool:
        """
        Convenience method:

        register nodes
            ↓
        create edge
            ↓
        add edge
        """

        self.add_node(
            parent
        )

        self.add_node(
            child
        )

        edge = (
            DiscoveryEdge.from_nodes(
                parent=parent,
                child=child,
                method=method,
                relation=relation,
                tool=tool,
                reason=reason,
                metadata=metadata,
            )
        )

        return self.add_edge(
            edge
        )

    # ==========================================================
    # Path lookup
    # ==========================================================

    def find_path_to(
        self,
        object_type: DiscoveryObjectType,
        object_id: str,
    ) -> DiscoveryPath | None:
        """
        Return deterministic shortest path from any
        explicitly registered root to the target.

        Disconnected non-root nodes return None.
        """

        target_key = self._make_key(
            object_type,
            object_id,
        )

        if (
            target_key
            not in
            self._nodes
        ):

            return None

        roots = sorted(
            self._root_keys,
            key=self._node_key_sort,
        )

        if not roots:

            return None

        # Explicit root target.
        if target_key in self._root_keys:

            return DiscoveryPath(
                case_id=self.case_id,
                nodes=(
                    self._nodes[
                        target_key
                    ],
                ),
                edges=(),
            )

        queue = deque()

        visited: set[
            tuple[
                DiscoveryObjectType,
                str,
            ]
        ] = set()

        for root_key in roots:

            queue.append(
                (
                    root_key,
                    (
                        root_key,
                    ),
                    (),
                )
            )

            visited.add(
                root_key
            )

        while queue:

            (
                current_key,
                node_path,
                edge_path,
            ) = queue.popleft()

            outgoing = sorted(
                self._outgoing_edges(
                    current_key
                ),
                key=self._edge_sort_key,
            )

            for edge in outgoing:

                child_key = (
                    edge.child_key
                )

                if child_key in visited:

                    continue

                next_node_path = (
                    node_path
                    +
                    (
                        child_key,
                    )
                )

                next_edge_path = (
                    edge_path
                    +
                    (
                        edge,
                    )
                )

                if (
                    child_key
                    ==
                    target_key
                ):

                    return DiscoveryPath(
                        case_id=(
                            self.case_id
                        ),
                        nodes=tuple(
                            self._nodes[
                                key
                            ]
                            for key
                            in next_node_path
                        ),
                        edges=(
                            next_edge_path
                        ),
                    )

                visited.add(
                    child_key
                )

                queue.append(
                    (
                        child_key,
                        next_node_path,
                        next_edge_path,
                    )
                )

        return None

    def has_path_to(
        self,
        object_type: DiscoveryObjectType,
        object_id: str,
    ) -> bool:

        return (
            self.find_path_to(
                object_type,
                object_id,
            )
            is not None
        )

    # ==========================================================
    # Views
    # ==========================================================

    @property
    def nodes(
        self,
    ) -> tuple[
        DiscoveryNode,
        ...,
    ]:

        return tuple(
            self._nodes[
                key
            ]
            for key
            in sorted(
                self._nodes,
                key=self._node_key_sort,
            )
        )

    @property
    def edges(
        self,
    ) -> tuple[
        DiscoveryEdge,
        ...,
    ]:

        return tuple(
            sorted(
                self._edges,
                key=self._edge_sort_key,
            )
        )

    @property
    def roots(
        self,
    ) -> tuple[
        DiscoveryNode,
        ...,
    ]:

        return tuple(
            self._nodes[
                key
            ]
            for key
            in sorted(
                self._root_keys,
                key=self._node_key_sort,
            )
        )

    @property
    def node_count(
        self,
    ) -> int:

        return len(
            self._nodes
        )

    @property
    def edge_count(
        self,
    ) -> int:

        return len(
            self._edges
        )

    @property
    def root_count(
        self,
    ) -> int:

        return len(
            self._root_keys
        )

    # ==========================================================
    # Cycle detection
    # ==========================================================

    def _path_exists(
        self,
        *,
        start: tuple[
            DiscoveryObjectType,
            str,
        ],
        target: tuple[
            DiscoveryObjectType,
            str,
        ],
    ) -> bool:

        if start == target:

            return True

        stack = [
            start
        ]

        visited = {
            start
        }

        while stack:

            current = (
                stack.pop()
            )

            for edge in self._outgoing_edges(
                current
            ):

                child = (
                    edge.child_key
                )

                if child == target:

                    return True

                if child in visited:

                    continue

                visited.add(
                    child
                )

                stack.append(
                    child
                )

        return False

    # ==========================================================
    # Internal graph helpers
    # ==========================================================

    def _outgoing_edges(
        self,
        key: tuple[
            DiscoveryObjectType,
            str,
        ],
    ) -> list[
        DiscoveryEdge
    ]:

        return [
            edge
            for edge
            in self._edges
            if (
                edge.parent_key
                ==
                key
            )
        ]

    def _validate_node_case(
        self,
        node: DiscoveryNode,
    ) -> None:

        if not isinstance(
            node,
            DiscoveryNode,
        ):

            raise TypeError(
                "node must be a DiscoveryNode."
            )

        if (
            node.case_id
            !=
            self.case_id
        ):

            raise ValueError(
                "Cross-case DiscoveryNode "
                "is not allowed."
            )

    @staticmethod
    def _make_key(
        object_type: DiscoveryObjectType,
        object_id: str,
    ) -> tuple[
        DiscoveryObjectType,
        str,
    ]:

        if not isinstance(
            object_type,
            DiscoveryObjectType,
        ):

            raise TypeError(
                "object_type must be a "
                "DiscoveryObjectType."
            )

        object_id = str(
            object_id
        ).strip()

        if not object_id:

            raise ValueError(
                "object_id cannot be empty."
            )

        return (
            object_type,
            object_id,
        )

    @staticmethod
    def _node_key_sort(
        key: tuple[
            DiscoveryObjectType,
            str,
        ],
    ) -> tuple[
        str,
        str,
    ]:

        return (
            key[
                0
            ].value,
            key[
                1
            ],
        )

    @staticmethod
    def _edge_sort_key(
        edge: DiscoveryEdge,
    ) -> tuple[
        str,
        str,
        str,
        str,
        str,
        str,
        str,
    ]:

        return (
            edge.parent_type.value,
            edge.parent_id,
            edge.child_type.value,
            edge.child_id,
            edge.method.value,
            edge.relation,
            edge.tool
            or "",
        )