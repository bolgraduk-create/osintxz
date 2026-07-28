"""
Nmap connector.

Performs network scanning using Nmap.

Responsibilities:

- execute Nmap
- parse XML output
- convert output to OsintResult

Does NOT:

- store database objects
- call AI
"""

from __future__ import annotations

import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from app.osint.base_connector import BaseConnector
from app.osint.models import (
    ConnectorRequest,
    OsintTargetType,
)
from app.osint.result import (
    OsintFinding,
    OsintResult,
    ResultStatus,
)
from app.osint.runner import ToolRunner


class NmapConnector(BaseConnector):
    """
    Nmap connector.
    """

    @property
    def name(
        self,
    ) -> str:

        return "Nmap"

    @property
    def description(
        self,
    ) -> str:

        return (
            "Performs TCP service "
            "discovery using Nmap."
        )

    @property
    def supported_targets(
        self,
    ) -> set[OsintTargetType]:

        return {
            OsintTargetType.IP,
            OsintTargetType.DOMAIN,
        }

    def __init__(
        self,
    ) -> None:

        self.runner = ToolRunner()

    def is_available(
        self,
    ) -> bool:

        return (
            shutil.which(
                "nmap",
            )
            is not None
        )

    def execute(
        self,
        request: ConnectorRequest,
    ) -> OsintResult:

        if (
            request.target.target_type
            not in self.supported_targets
        ):
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported target.",
            )

        if not self.is_available():

            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_AVAILABLE,
                error="Nmap is not installed.",
            )

        with tempfile.TemporaryDirectory() as temp:

            xml_file = Path(temp) / "scan.xml"

            execution = self.runner.run(

                command=[
                    "nmap",
                    "-Pn",
                    "-sV",
                    "-oX",
                    str(xml_file),
                    request.target.value,
                ],

                timeout=request.timeout,

            )

            if not execution.success:

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.FAILED,

                    execution_time=execution.execution_time,

                    error=execution.stderr,

                )

            if not xml_file.exists():

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.PARTIAL,

                    execution_time=execution.execution_time,

                    error="XML report not produced.",

                )

            try:

                root = ET.parse(
                    xml_file,
                ).getroot()

            except Exception as exc:

                return OsintResult(

                    connector=self.name,

                    status=ResultStatus.PARTIAL,

                    execution_time=execution.execution_time,

                    error=str(exc),

                )

        findings: list[OsintFinding] = []

        for host in root.findall("host"):

            for port in host.findall("./ports/port"):

                state = port.find("state")

                if state is None:
                    continue

                if state.attrib.get("state") != "open":
                    continue

                service = port.find("service")

                findings.append(

                    OsintFinding(

                        category="open_port",

                        value=port.attrib.get(
                            "portid",
                            "",
                        ),

                        source="Nmap",

                        confidence=1.0,

                        reliability=1.0,

                        metadata={

                            "protocol": port.attrib.get(
                                "protocol",
                            ),

                            "service": (
                                service.attrib.get("name")
                                if service is not None
                                else None
                            ),

                            "product": (
                                service.attrib.get("product")
                                if service is not None
                                else None
                            ),

                            "version": (
                                service.attrib.get("version")
                                if service is not None
                                else None
                            ),

                        },

                    )

                )

        result = OsintResult(

            connector=self.name,

            status=ResultStatus.SUCCESS,

            execution_time=execution.execution_time,

            findings=findings,

            raw_data=(
                xml_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
                if request.save_raw_output
                else None
            ),

        )

        result.metadata = {

            "open_ports": result.total_findings,

        }

        return result