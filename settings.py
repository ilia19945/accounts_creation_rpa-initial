import environ
import os
from elasticsearch import AsyncElasticsearch

env = environ.Env(
    DEBUG=(bool, True)
)

# Set the project base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Take environment variables from .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


es = AsyncElasticsearch([{
    'host': env('ES_HOST'),
    'port': env('ES_PORT'),
}])


jira_api = 'Basic aWx5YS5rb25vdmFsb3ZAanVuZWhvbWVzLmNvbTpyZ05hRGIyZnZkOUxCcktKckZMYzcyMjY='
amazon_api = ''
