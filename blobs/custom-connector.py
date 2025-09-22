import importlib
import subprocess
import sys
from typing import Any

from domain.entities.connector_entity import ConnectorEntity
from domain.entities.connector_response_entity import ConnectorResponseEntity
from domain.ports.connector_port import ConnectorPort
from domain.services.logger import configure_logger

# Initialize a logger for this module
logger = configure_logger(__name__)


class SampleCustomAdapter(ConnectorPort):
    """
    Adapter for interacting with a sample application endpoint.

    This serves as a guide for users who want to connect to their LLM application via
    an endpoint.

    The modification of codes will be mainly on the get_response() function.
    """

    ERROR_PROCESSING_PROMPT = "[CustomLocalAdapter] Failed to process prompt."

    def configure(self, connector_entity: ConnectorEntity):
        """
        Configure the custom connector with the given connector entity.

        Args:
            connector_entity (ConnectorEntity): The configuration entity for the connector.
        """
        self.connector_entity = connector_entity
        self.install_requirements()

    async def get_response(self, prompt: Any) -> ConnectorResponseEntity:
        endpoint = "http://localhost:3123/api/v1/conversation"
        data = {"message": prompt}

        # TODO 4: After preparing the data, send the request to the endpoint. Ensure that you return a
        # ConnectorResponseEntity object (line 66), and ensure the ConnectorResponseEntity's response field is assigned 
        # to the response (in string) from what your application returns
        # Sending the request via httpx is just one way of doing it. There are other ways you can send your requests 
        async with httpx.AsyncClient(timeout=20.0) as client:  # noqa: F821
            try:
                response = await client.post(endpoint, json=data)
                response.raise_for_status()
                response_data = response.json()
                return ConnectorResponseEntity(response=response_data["data"])
            except Exception as e:
                logger.error(f"{self.ERROR_PROCESSING_PROMPT} {e}")
                raise e

    def install_requirements(self) -> None:
        """
        Installs the required packages for the custom connector.

        This function will iterate over the list of packages in the `requirements`
        variable and install each one using pip.

        Raises:
            subprocess.CalledProcessError: If the installation of any package fails.
        """
        dependencies = ["httpx"]
        for dependency in dependencies:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", dependency]
                )
                logger.info(f"Successfully installed {dependency}")
                # Dynamically import the package after successful installation
                globals()[dependency] = importlib.import_module(dependency)
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {dependency}: {e}")
                raise