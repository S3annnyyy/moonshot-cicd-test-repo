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

# This is a sample connector template to refer to for creating your own custom connector
# To test this connector, we will require the Python file examples/sample_llm_application/sample_llm_application.py.
# Refer to sample_llm_application.py for more information.

# How to use this sample to make your own connector:
#       Step 1 - Make a copy of this file and put it in your S3.
#       Step 2 - Change the file name and the class name to what you want.
#       Step 3 - Look for TODOs in this file, and modify the code according to what your LLM application needs.
#       Step 4 - Update moonshot_config.yaml or your own Moonshot config file to include your new connector.
#                Refer to our moonshot_config.yaml template for sample.

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
        # TODO 2: Input the endpoint to your LLM application.
        endpoint = ""

        # TODO 3: Prepare the data to be sent in the request. The format of the data should match what you are
        # expecting in your application endpoint. Replace with the format you are expecting
        data = {"input_prompt": prompt}

        # TODO 4: After preparing the data, send the request to the endpoint. Ensure that you return a
        # ConnectorResponseEntity object (line 66), and ensure the ConnectorResponseEntity's response field is assigned 
        # to the response (in string) from what your application returns
        # Sending the request via httpx is just one way of doing it. There are other ways you can send your requests 
        async with httpx.AsyncClient(timeout=20.0) as client:  # noqa: F821
            try:
                response = await client.post(endpoint, json=data)
                response.raise_for_status()
                response_data = response.json()
                return ConnectorResponseEntity(response=response_data["response"])
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
        # TODO 5 (Optional): If your custom connector has dependencies, add them into the list below. We will attempt
        # to install and import the packages. In this example, our dependency is the library 'httpx'.
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