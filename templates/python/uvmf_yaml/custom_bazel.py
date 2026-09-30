"""Whole-file customization for generated Bazel definitions."""

import os
import re


BAZEL_BLOCK = 'bazel_file'
BAZEL_BEGIN = '# pragma uvmf custom '+BAZEL_BLOCK+' begin\n'
BAZEL_END = '# pragma uvmf custom '+BAZEL_BLOCK+' end\n'
CUSTOM_MARKER = re.compile(r'^\s*(?:#+|//+) pragma uvmf custom \w+ (?:begin|end)')


def is_bazel_file(path):
  return os.path.basename(path) in ('BUILD','BUILD.bazel','WORKSPACE','WORKSPACE.bazel','MODULE.bazel') or path.endswith('.bzl')


def bazel_custom_content(text):
  """Retain all code/comments; retire only legacy custom-marker lines.

  The normal regeneration parser validates the old markers first. Flattening
  them prevents nested blocks and preserves edits outside the old small slots.
  """
  content = ''.join(line for line in text.splitlines(True) if not CUSTOM_MARKER.match(line))
  if content and not content.endswith('\n'):
    content += '\n'
  return content


def wrap_bazel_file(text):
  return BAZEL_BEGIN+bazel_custom_content(text)+BAZEL_END
