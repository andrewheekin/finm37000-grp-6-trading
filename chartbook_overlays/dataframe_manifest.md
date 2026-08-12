| Dataframe Name                 | {{dataframe_manifest.dataframe_name}}                                                   |
|--------------------------------|--------------------------------------------------------------------------------------|
| Dataframe ID                   | `{{pipeline_id}}:{{dataframe_id}}`                                       |
| Data Sources                   | {{dataframe_manifest.data_sources | join(', ')}}                                        |
| Data Providers                 | {{dataframe_manifest.data_providers | join(', ')}}                                      |
| Links to Providers             | {{dataframe_manifest.links_to_data_providers | join(', ')}}                             |
| Topic Tags                     | {{dataframe_manifest.topic_tags | join(', ')}}                                          |
| How is data pulled?            | {{dataframe_manifest.how_is_pulled}}                                                    |
| Dataframe Path                 | `{{dataframe_manifest.path_to_parquet_data}}`                                                   |
{% if enable_data_download %}
| Download Data as Parquet       | [Parquet](../../download_dataframe/{{pipeline_id}}/{{dataframe_id}}.parquet)         |
| Download Data as Excel         | [Excel](../../download_dataframe/{{pipeline_id}}/{{dataframe_id}}.xlsx)              |
{% endif %}
