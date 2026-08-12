# {{pipeline_manifest.pipeline.pipeline_name}}

FINM 37000 | Summer 2026 | Group 6

By Michael Dowling, Andrew Heekin, Bhuvanesh Kodem, Sam Zhang

{% if index_toc_content %}
{{ index_toc_content }}
{% elif site_pages_list %}
```{toctree}
:maxdepth: 2
:caption: Site Pages
:hidden:
{{ site_pages_list | join("\n")}}
```
{% endif %}

```{toctree}
:maxdepth: 1
:caption: Notebooks
:hidden:
{{ notebook_list | join("\n")}}
```

{% if notes_list %}
```{toctree}
:maxdepth: 1
:caption: Notes
:hidden:
{{ notes_list | join("\n")}}
```
{% endif %}

```{toctree}
:maxdepth: 1
:caption: Pipeline Dataframes
:hidden:
{{dataframe_file_list | sort | join("\n")}}
```

```{toctree}
:maxdepth: 1
:caption: Appendix
:hidden:
myst_markdown_demos.md
apidocs/index
```

{{readme_text}}
