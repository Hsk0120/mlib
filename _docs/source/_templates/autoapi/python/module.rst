{#-
  mlib のモジュール/パッケージページ。
  独自の書式にするのは mlib.cmds(コマンド一覧)と mlib.cmds.<コマンド名>(各コマンド)だけ。
  それ以外は sphinx-autoapi に同梱された既定テンプレートへそのまま委ねる。
  "autoapi-packaged/" 接頭辞は _ext/mlibDocs.py の prepare_autoapi で登録している。
-#}
{% set command_package = package_name ~ ".cmds" %}
{% if obj.id == command_package %}
{{ package_name }} コマンドリファレンス
{{ "=" * (package_name|length + 30) }}

.. py:module:: {{ command_package }}

``{{ command_package }}.<コマンド名>()`` と ``{{ package_name }}.<コマンド名>()`` は同じ関数です。

.. toctree::
   :maxdepth: 1

{% for command_module in obj.submodules|sort %}
   {{ command_module.include_path }}
{% endfor %}

{% elif obj.id.startswith(command_package ~ ".") %}
{#-
  取得コマンドはcmdsとルートの公開入口を、同じ署名・説明にまとめる。
  説明・Args・Returns・Raises・Examples はすべて関数のdocstringに書き、モジュールのdocstringは1行にする。
  モジュールのdocstringは、同名の関数が見つからないときだけ出す(関数の説明と二重にしないため)。
-#}
{% set command_name = obj.short_name %}
{% set entry_point = obj.functions|selectattr("short_name", "equalto", command_name)|first %}
{{ command_name }}
{{ "=" * command_name|length }}

.. py:module:: {{ obj.name }}
   :no-index:

{% if entry_point %}
.. py:currentmodule:: {{ package_name }}

.. py:function:: {{ command_name }}({{ entry_point.args }})
                 cmds.{{ command_name }}({{ entry_point.args }})
   :no-index-entry:

   {{ entry_point.docstring|indent(3) }}

{% else %}
.. autoapi-nested-parse::

   {{ obj.docstring|indent(3) }}

{% endif %}

{% else %}
{% include "autoapi-packaged/python/module.rst" %}
{% endif %}
