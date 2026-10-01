from unittest.mock import patch

from agents.self_help_agent import SelfHelpAgent


def test_bedrock_client_uses_default_aws_credentials_provider():
    with patch.dict("os.environ", {
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_REGION": "us-east-1",
    }):
        with patch("agents.self_help_agent.boto3.client") as create_client:
            agent = SelfHelpAgent(region_name="us-east-1")

            client = agent.client

    assert client is create_client.return_value
    create_client.assert_called_once_with("bedrock-runtime", region_name="us-east-1")