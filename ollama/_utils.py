from __future__ import annotations

from typing import Any, Callable, List, Mapping, Optional, Sequence, Union, get_args, get_origin
from ollama._types import Tool

# Map both the type and the type reference to the same JSON type
PYTHON_TO_JSON_TYPES = {
  int: 'integer',
  'int': 'integer',
  str: 'string',
  'str': 'string',
  float: 'number',
  'float': 'number',
  bool: 'boolean',
  'bool': 'boolean',
  list: 'array',
  'list': 'array',
  dict: 'object',
  'dict': 'object',
  type(None): 'null',
  'None': 'null',
}

"""
TODO:
- Testing - varying cases for functions and parsing
- Default to string if type is unknown - define behavior
- Add future importing stuff

"""


def _get_json_type(python_type: Any) -> str | List[str]:
  # Print for debugging

  # Handle Optional types (Union[type, None] and type | None)
  origin = get_origin(python_type)
  if origin is type(int | str) or origin is Union:
    args = get_args(python_type)
    # Filter out None/NoneType from union args
    non_none_args = [arg for arg in args if arg not in (None, type(None))]
    if non_none_args:
      if len(non_none_args) == 1:
        return _get_json_type(non_none_args[0])
      else:
        return [_get_json_type(arg) for arg in non_none_args]
    return 'null'

  # Direct type check first (like int, str, etc.)
  if python_type in PYTHON_TO_JSON_TYPES:
    return PYTHON_TO_JSON_TYPES[python_type]

  # Handle typing.List, typing.Dict etc.
  if origin is not None:
    return PYTHON_TO_JSON_TYPES.get(origin, 'string')

  # Default to string if type is unknown
  raise ValueError(f'Unknown type: {python_type}')


#   return 'string'


def _is_optional_type(python_type: Any) -> bool:
  origin = get_origin(python_type)
  if origin is type(int | str) or origin is Union:
    args = get_args(python_type)
    return any(arg in (None, type(None)) for arg in args)
  return False


def convert_function_to_tool(func: Callable) -> Tool:
  doc_string = func.__doc__
  if not doc_string:
    raise ValueError(f'Function {func.__name__} must have a docstring in Google format. Example:\n' '"""Add two numbers.\n\n' 'Args:\n' '    a: First number\n' '    b: Second number\n\n' 'Returns:\n' '    int: Sum of the numbers\n' '"""')

  # Extract description from docstring - get all lines before Args:
  description_lines = []
  for line in doc_string.split('\n'):
    line = line.strip()
    if line.startswith('Args:'):
      break
    if line:
      description_lines.append(line)

  description = ' '.join(description_lines).strip()

  # Parse Args section
  if 'Args:' not in doc_string:
    raise ValueError(f'Function {func.__name__} docstring must have an Args section in Google format')

  args_section = doc_string.split('Args:')[1]
  if 'Returns:' in args_section:
    args_section = args_section.split('Returns:')[0]

  parameters = {'type': 'object', 'properties': {}, 'required': []}

  # Build parameters dict
  for param_name, param_type in func.__annotations__.items():
    if param_name == 'return':
      continue

    param_desc = None
    for line in args_section.split('\n'):
      line = line.strip()
      # Check for parameter name with or without colon, space, or parentheses to mitigate formatting issues
      if line.startswith(param_name + ':') or line.startswith(param_name + ' ') or line.startswith(param_name + '('):
        param_desc = line.split(':', 1)[1].strip()
        break

    if not param_desc:
      raise ValueError(f'Parameter {param_name} must have a description in the Args section')

    parameters['properties'][param_name] = {
      'type': _get_json_type(param_type),
      'description': param_desc,
    }

    # Only add to required if not optional - could capture and map earlier to save this call
    if not _is_optional_type(param_type):
      parameters['required'].append(param_name)

  tool_dict = {
    'type': 'function',
    'function': {
      'name': func.__name__,
      'description': description,
      'parameters': parameters,
    },
  }
  return Tool.model_validate(tool_dict)


def process_tools(tools: Optional[Sequence[Union[Mapping[str, Any], Tool, Callable]]] = None) -> Sequence[Tool]:
  if not tools:
    return []

  processed_tools = []
  for tool in tools:
    if callable(tool):
      processed_tools.append(convert_function_to_tool(tool))
    else:
      # Existing tool handling logic
      processed_tools.append(Tool.model_validate(tool))

  return processed_tools
