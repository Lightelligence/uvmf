"""Opt-in, insertion-only migration into adjacent SV customization slots.

This is deliberately not a three-way merge. Without a generator baseline,
replacements, deletions and additions at unsupported positions are ambiguous.
"""

from difflib import SequenceMatcher
import re

from uvmf_gen import UserError


PRAGMA = re.compile(r'^\s*//+ pragma uvmf custom (\w+) (begin|end)')
SUPPORTED_SLOTS = {
  'package_item_after_configuration',
  'class_item_before_sequencer',
  'build_phase_components',
  'new_pre_config',
}


def _scaffold(text):
  """Retain nonblank outside lines, plus exact source offsets and block slots."""
  raw = text.splitlines(True)
  lines, offsets, slots = [], [], {}
  active = None
  for offset,line in enumerate(raw):
    match = PRAGMA.match(line)
    if match:
      label,kind = match.groups()
      if kind == 'begin':
        if active is not None or label in slots:
          raise UserError('Invalid custom blocks while migrating unmarked code')
        active = label
        slots[label] = {'position': len(lines), 'begin': offset}
      else:
        if active != label:
          raise UserError('Invalid custom blocks while migrating unmarked code')
        slots[label]['end'] = offset
        active = None
      continue
    if active is None and line.strip():
      lines.append(line.rstrip())
      offsets.append(offset)
  if active is not None:
    raise UserError('Unclosed custom block while migrating unmarked code')
  return raw,lines,offsets,slots


def migrate_unmarked(old_text,new_text,filename):
  """Return {label: {before, after}} or refuse an unsafe scaffold difference.

  Only additions immediately adjacent to an approved slot are accepted. The
  generated scaffold must otherwise be identical. Keeping the same position
  avoids reordering declarations, initialization or package dependencies.
  """
  old_raw,old_lines,old_offsets,old_slots = _scaffold(old_text)
  _,new_lines,_,new_slots = _scaffold(new_text)
  migrations = {}
  matcher = SequenceMatcher(a=new_lines,b=old_lines,autojunk=False)
  for kind,new_start,new_end,old_start,old_end in matcher.get_opcodes():
    if kind == 'equal':
      continue
    candidates = [
      label for label,slot in new_slots.items()
      if label in SUPPORTED_SLOTS and slot['position'] == new_start
    ]
    if kind != 'insert' or len(candidates) != 1:
      old_line = old_offsets[old_start]+1 if old_start < len(old_offsets) else len(old_raw)+1
      raise UserError(
        'Cannot safely migrate unmarked code: {0}:{1}. Only additions adjacent '
        'to a supported custom block are accepted; move the edits into custom '
        'blocks manually or restore the matching generated scaffold.'.format(filename,old_line)
      )
    label = candidates[0]
    start,end = old_offsets[old_start],old_offsets[old_end-1]+1
    # Do not collapse an insertion across a pre-existing custom block. It has
    # two different execution positions even if blank outside lines coincide.
    if any(start <= slot['begin'] < end for slot in old_slots.values()):
      raise UserError('Ambiguous unmarked additions across a custom block: '+filename)
    # Newly introduced slots must not move additions across another retained
    # custom block at the same scaffold boundary (e.g. register-model build).
    for other_label in old_slots.keys() & new_slots.keys():
      if other_label == label:
        continue
      old_before = end <= old_slots[other_label]['begin']
      new_before = new_slots[label]['begin'] < new_slots[other_label]['begin']
      if old_before != new_before:
        raise UserError('Migration would reorder code across custom block {0}: {1}'.format(other_label,filename))
    content = ''.join(old_raw[start:end])
    if not content.endswith('\n'):
      content += '\n'
    old_slot = old_slots.get(label)
    side = 'after' if old_slot and start > old_slot['end'] else 'before'
    parts = migrations.setdefault(label,{'before': '', 'after': ''})
    parts[side] += content
  return migrations
