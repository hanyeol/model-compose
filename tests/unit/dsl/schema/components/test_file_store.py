"""Tests for file-store component and action schemas."""

import pytest
from pydantic import ValidationError, TypeAdapter

from mindor.dsl.schema.component import (
    ComponentConfig,
    FileStoreComponentConfig,
    LocalFileStoreComponentConfig,
    AwsS3FileStoreComponentConfig,
    GcpStorageFileStoreComponentConfig,
    AzureBlobFileStoreComponentConfig,
    FileStoreDriver,
)
from mindor.dsl.schema.action import (
    FileStoreActionConfig,
    LocalFileStoreActionConfig,
    AwsS3FileStoreActionConfig,
    GcpStorageFileStoreActionConfig,
    AzureBlobFileStoreActionConfig,
    FileStoreActionMethod,
    LocalFilePutActionConfig,
    LocalFileGetActionConfig,
    LocalFileDeleteActionConfig,
    LocalFileExistsActionConfig,
    LocalFileListActionConfig,
    AwsS3FilePutActionConfig,
    GcpStorageFilePutActionConfig,
    AzureBlobFilePutActionConfig,
)


ComponentAdapter = TypeAdapter(ComponentConfig)
LocalActionAdapter = TypeAdapter(LocalFileStoreActionConfig)
AwsS3ActionAdapter = TypeAdapter(AwsS3FileStoreActionConfig)
GcpStorageActionAdapter = TypeAdapter(GcpStorageFileStoreActionConfig)
AzureBlobActionAdapter = TypeAdapter(AzureBlobFileStoreActionConfig)


class TestFileStoreComponentSchema:
    def test_minimal_local_config(self):
        config = ComponentAdapter.validate_python({
            "id": "files",
            "type": "file-store",
            "driver": "local",
            "actions": [],
        })
        assert isinstance(config, LocalFileStoreComponentConfig)
        assert config.driver == FileStoreDriver.LOCAL
        assert config.base_path is None

    def test_local_with_base_path(self):
        config = ComponentAdapter.validate_python({
            "id": "files",
            "type": "file-store",
            "driver": "local",
            "base_path": "./storage",
            "actions": [],
        })
        assert config.base_path == "./storage"

    def test_minimal_aws_s3_config(self):
        config = ComponentAdapter.validate_python({
            "id": "s3",
            "type": "file-store",
            "driver": "aws-s3",
            "bucket": "my-bucket",
            "actions": [],
        })
        assert isinstance(config, AwsS3FileStoreComponentConfig)
        assert config.bucket == "my-bucket"
        assert config.region is None
        assert config.endpoint is None

    def test_full_aws_s3_config(self):
        config = ComponentAdapter.validate_python({
            "id": "s3",
            "type": "file-store",
            "driver": "aws-s3",
            "bucket": "my-bucket",
            "region": "ap-northeast-2",
            "endpoint": "https://r2.example.com",
            "access_key_id": "KEY",
            "secret_access_key": "SECRET",
            "session_token": "TOKEN",
            "base_path": "workflows/",
            "actions": [],
        })
        assert config.region == "ap-northeast-2"
        assert config.endpoint == "https://r2.example.com"
        assert config.access_key_id == "KEY"
        assert config.secret_access_key == "SECRET"
        assert config.session_token == "TOKEN"
        assert config.base_path == "workflows/"

    def test_aws_s3_requires_bucket(self):
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "s3",
                "type": "file-store",
                "driver": "aws-s3",
                "actions": [],
            })

    def test_minimal_gcp_storage_config(self):
        config = ComponentAdapter.validate_python({
            "id": "gcs",
            "type": "file-store",
            "driver": "gcp-storage",
            "bucket": "my-bucket",
            "actions": [],
        })
        assert isinstance(config, GcpStorageFileStoreComponentConfig)
        assert config.bucket == "my-bucket"
        assert config.project is None
        assert config.credentials_path is None

    def test_full_gcp_storage_config(self):
        config = ComponentAdapter.validate_python({
            "id": "gcs",
            "type": "file-store",
            "driver": "gcp-storage",
            "bucket": "my-bucket",
            "project": "my-project",
            "credentials_path": "./creds.json",
            "actions": [],
        })
        assert config.project == "my-project"
        assert config.credentials_path == "./creds.json"

    def test_minimal_azure_blob_config(self):
        config = ComponentAdapter.validate_python({
            "id": "azure",
            "type": "file-store",
            "driver": "azure-blob",
            "container": "my-container",
            "connection_string": "DefaultEndpointsProtocol=https;AccountName=x;AccountKey=y;",
            "actions": [],
        })
        assert isinstance(config, AzureBlobFileStoreComponentConfig)
        assert config.container == "my-container"

    def test_azure_blob_with_connection_string(self):
        config = ComponentAdapter.validate_python({
            "id": "azure",
            "type": "file-store",
            "driver": "azure-blob",
            "container": "my-container",
            "connection_string": "DefaultEndpointsProtocol=...",
            "actions": [],
        })
        assert config.connection_string == "DefaultEndpointsProtocol=..."

    def test_azure_blob_with_account_credentials(self):
        config = ComponentAdapter.validate_python({
            "id": "azure",
            "type": "file-store",
            "driver": "azure-blob",
            "container": "my-container",
            "account_name": "mystorage",
            "account_key": "mykey==",
            "actions": [],
        })
        assert config.account_name == "mystorage"
        assert config.account_key == "mykey=="

    def test_azure_blob_credentials_mutual_exclusion(self):
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "azure",
                "type": "file-store",
                "driver": "azure-blob",
                "container": "my-container",
                "connection_string": "x",
                "account_name": "y",
                "account_key": "z",
                "actions": [],
            })

    def test_invalid_driver(self):
        with pytest.raises(ValidationError):
            ComponentAdapter.validate_python({
                "id": "files",
                "type": "file-store",
                "driver": "unknown",
                "actions": [],
            })


class TestLocalFileStoreActionSchema:
    def test_put_action_minimal(self):
        config = LocalActionAdapter.validate_python({
            "method": "put",
            "path": "data/file.bin",
            "source": "${input.data}",
        })
        assert isinstance(config, LocalFilePutActionConfig)
        assert config.method == FileStoreActionMethod.PUT
        assert config.path == "data/file.bin"
        assert config.content_type is None
        assert config.metadata is None

    def test_put_action_full(self):
        config = LocalActionAdapter.validate_python({
            "id": "upload",
            "method": "put",
            "path": "images/${input.id}.png",
            "source": "${input.image_bytes}",
            "content_type": "image/png",
            "metadata": {"workflow": "abc"},
            "multipart_threshold": "16MB",
            "chunk_size": "4MB",
        })
        assert config.content_type == "image/png"
        assert config.metadata == {"workflow": "abc"}
        assert config.multipart_threshold == "16MB"
        assert config.chunk_size == "4MB"

    def test_get_action_minimal(self):
        config = LocalActionAdapter.validate_python({
            "method": "get",
            "path": "data/file.bin",
        })
        assert isinstance(config, LocalFileGetActionConfig)
        assert config.save_to is None
        assert config.streaming is False

    def test_get_action_with_save_to(self):
        config = LocalActionAdapter.validate_python({
            "method": "get",
            "path": "data/file.bin",
            "save_to": "/tmp/file.bin",
        })
        assert config.save_to == "/tmp/file.bin"

    def test_get_action_with_streaming(self):
        config = LocalActionAdapter.validate_python({
            "method": "get",
            "path": "data/file.bin",
            "streaming": True,
        })
        assert config.streaming is True

    def test_get_action_with_streaming_variable(self):
        config = LocalActionAdapter.validate_python({
            "method": "get",
            "path": "data/file.bin",
            "streaming": "${input.lazy}",
        })
        assert config.streaming == "${input.lazy}"

    def test_get_action_rejects_save_to_and_streaming(self):
        with pytest.raises(ValidationError, match="cannot both be set"):
            LocalActionAdapter.validate_python({
                "method": "get",
                "path": "data/file.bin",
                "save_to": "/tmp/x.bin",
                "streaming": True,
            })

    def test_get_action_allows_save_to_with_streaming_false(self):
        # explicit streaming: false alongside save_to is fine
        config = LocalActionAdapter.validate_python({
            "method": "get",
            "path": "data/file.bin",
            "save_to": "/tmp/x.bin",
            "streaming": False,
        })
        assert config.save_to == "/tmp/x.bin"
        assert config.streaming is False

    def test_get_action_allows_save_to_with_streaming_variable(self):
        # template strings are resolved at runtime, so we don't reject statically
        config = LocalActionAdapter.validate_python({
            "method": "get",
            "path": "data/file.bin",
            "save_to": "/tmp/x.bin",
            "streaming": "${input.lazy}",
        })
        assert config.save_to == "/tmp/x.bin"
        assert config.streaming == "${input.lazy}"

    def test_delete_action(self):
        config = LocalActionAdapter.validate_python({
            "method": "delete",
            "path": "data/file.bin",
        })
        assert isinstance(config, LocalFileDeleteActionConfig)

    def test_exists_action(self):
        config = LocalActionAdapter.validate_python({
            "method": "exists",
            "path": "data/file.bin",
        })
        assert isinstance(config, LocalFileExistsActionConfig)

    def test_list_action_minimal(self):
        config = LocalActionAdapter.validate_python({
            "method": "list",
        })
        assert isinstance(config, LocalFileListActionConfig)
        assert config.path is None
        assert config.max_result_count is None
        assert config.next_token is None

    def test_list_action_full(self):
        config = LocalActionAdapter.validate_python({
            "method": "list",
            "path": "images/",
            "max_result_count": 100,
            "next_token": "abc",
        })
        assert config.path == "images/"
        assert config.max_result_count == 100
        assert config.next_token == "abc"

    def test_action_discriminator(self):
        cases = [
            ({"method": "put", "path": "x", "source": "y"}, LocalFilePutActionConfig),
            ({"method": "get", "path": "x"}, LocalFileGetActionConfig),
            ({"method": "delete", "path": "x"}, LocalFileDeleteActionConfig),
            ({"method": "exists", "path": "x"}, LocalFileExistsActionConfig),
            ({"method": "list"}, LocalFileListActionConfig),
        ]
        for data, expected_type in cases:
            config = LocalActionAdapter.validate_python(data)
            assert isinstance(config, expected_type), f"Expected {expected_type} for {data['method']}"


class TestCloudDriverActionSchemas:
    def test_aws_s3_actions(self):
        cases = [
            {"method": "put", "path": "x", "source": "y"},
            {"method": "get", "path": "x"},
            {"method": "delete", "path": "x"},
            {"method": "exists", "path": "x"},
            {"method": "list"},
        ]
        for data in cases:
            AwsS3ActionAdapter.validate_python(data)

    def test_gcp_storage_actions(self):
        cases = [
            {"method": "put", "path": "x", "source": "y"},
            {"method": "get", "path": "x"},
            {"method": "delete", "path": "x"},
            {"method": "exists", "path": "x"},
            {"method": "list"},
        ]
        for data in cases:
            GcpStorageActionAdapter.validate_python(data)

    def test_azure_blob_actions(self):
        cases = [
            {"method": "put", "path": "x", "source": "y"},
            {"method": "get", "path": "x"},
            {"method": "delete", "path": "x"},
            {"method": "exists", "path": "x"},
            {"method": "list"},
        ]
        for data in cases:
            AzureBlobActionAdapter.validate_python(data)


class TestFileStoreIntegration:
    def test_local_component_with_actions(self):
        config = ComponentAdapter.validate_python({
            "id": "files",
            "type": "file-store",
            "driver": "local",
            "base_path": "./storage",
            "actions": [
                {"id": "save", "method": "put", "path": "${input.name}", "source": "${input.data}"},
                {"id": "load", "method": "get", "path": "${input.name}"},
                {"id": "remove", "method": "delete", "path": "${input.name}"},
                {"id": "check", "method": "exists", "path": "${input.name}"},
                {"id": "scan", "method": "list", "path": "data/"},
            ],
        })
        assert isinstance(config, LocalFileStoreComponentConfig)
        assert len(config.actions) == 5
        assert isinstance(config.actions[0], LocalFilePutActionConfig)
        assert isinstance(config.actions[1], LocalFileGetActionConfig)
        assert isinstance(config.actions[2], LocalFileDeleteActionConfig)
        assert isinstance(config.actions[3], LocalFileExistsActionConfig)
        assert isinstance(config.actions[4], LocalFileListActionConfig)

    def test_aws_s3_component_with_actions(self):
        config = ComponentAdapter.validate_python({
            "id": "s3",
            "type": "file-store",
            "driver": "aws-s3",
            "bucket": "my-bucket",
            "region": "us-east-1",
            "actions": [
                {
                    "id": "upload-image",
                    "method": "put",
                    "path": "images/${input.id}.png",
                    "source": "${input.image_bytes}",
                    "content_type": "image/png",
                    "metadata": {"workflow": "${context.workflow_id}"},
                },
            ],
        })
        assert isinstance(config, AwsS3FileStoreComponentConfig)
        assert isinstance(config.actions[0], AwsS3FilePutActionConfig)

    def test_single_action_inflate(self):
        config = ComponentAdapter.validate_python({
            "id": "files",
            "type": "file-store",
            "driver": "local",
            "action": {
                "method": "put",
                "path": "x",
                "source": "y",
            },
        })
        assert len(config.actions) == 1
        assert isinstance(config.actions[0], LocalFilePutActionConfig)
