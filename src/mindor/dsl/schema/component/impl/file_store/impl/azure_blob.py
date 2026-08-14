from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import AzureBlobFileStoreActionConfig
from .common import CommonFileStoreComponentConfig, FileStoreDriver

class AzureBlobFileStoreComponentConfig(CommonFileStoreComponentConfig):
    driver: Literal[FileStoreDriver.AZURE_BLOB]
    container: str = Field(..., description="Name of the Azure Blob container that backs this store.")
    connection_string: Optional[str] = Field(default=None, description="Azure Storage connection string. Mutually exclusive with `account_name` and `account_key`.")
    account_name: Optional[str] = Field(default=None, description="Azure Storage account name. Used when `connection_string` is unset.")
    account_key: Optional[str] = Field(default=None, description="Azure Storage account key. Used when `connection_string` is unset.")
    actions: List[AzureBlobFileStoreActionConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def validate_auth(cls, values: Dict[str, Any]):
        if values.get("connection_string") and (values.get("account_name") or values.get("account_key")):
            raise ValueError("Specify either 'connection_string' or '(account_name, account_key)', not both")
        if not values.get("connection_string") and not values.get("account_name"):
            raise ValueError("Either 'connection_string' or 'account_name' must be provided")
        return values
