#!/bin/python3

import sys

from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError
from azure.kusto.data.helpers import dataframe_from_result_table

from azure.kusto.ingest.status import KustoIngestStatusQueues
from azure.kusto.data import DataFormat
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties, FileDescriptor, ReportLevel, ReportMethod

cluster = "https://sonic.westus2.kusto.windows.net"
kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(cluster)
client = KustoClient(kcsb)

ingest_cluster = "https://ingest-sonic.westus2.kusto.windows.net"
ingest_kcsb = KustoConnectionStringBuilder.with_az_cli_authentication(ingest_cluster)
ingest_client = QueuedIngestClient(ingest_kcsb)

def sii_org():
    with open('kusto_sii_org.kql') as f:
        query=f.read()

    response = client.execute_query('sonic-buildimage-prs', query)
    
    print("Organization,Score")
    for row in response.primary_results[0]:
        print("{},{}".format(row[0],row[1]))

def sii_person():
    with open('kusto_sii_person.kql') as f:
        query=f.read()

    response = client.execute_query('sonic-buildimage-prs', query)

    print("Individual,Score")
    for row in response.primary_results[0]:
        print("{},{}".format(row[0],row[1]))

def sii_author_clear():
    query = ".clear table author data"
    response = client.execute('sonic-buildimage-prs', query)
    print(response.primary_results[0])

def sii_author_import():
    properties = IngestionProperties(database="sonic-buildimage-prs", table="author", data_format=DataFormat.CSV, ingestion_mapping_reference="mapping1", additional_properties={'ignoreFirstRecord': 'false'})
    response = ingest_client.ingest_from_file('sii_author_map/author.csv', properties)
    print(response)
    query = "author | count"
    response = client.execute('sonic-buildimage-prs', query)
    print(response.primary_results[0])

def sii_author():
    query = "author | count"
    response = client.execute('sonic-buildimage-prs', query)
    print(response.primary_results[0])
    

if __name__ == '__main__':
    if sys.argv[1] == "sii_org":
        sii_org()
    if sys.argv[1] == "sii_person":
        sii_person()
    if sys.argv[1] == "sii_author_clear":
        sii_author_clear()
    if sys.argv[1] == "sii_author_import":
        sii_author_import()
    if sys.argv[1] == "sii_author":
        sii_author()
