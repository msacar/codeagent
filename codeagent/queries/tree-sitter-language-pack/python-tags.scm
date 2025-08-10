; Python tags for code navigation and context
; Captures definitions that can be used for code indexing

; Classes
(class_definition
  name: (identifier) @name.definition.class)

; Functions
(function_definition
  name: (identifier) @name.definition.function)

; Methods (functions inside classes)
(class_definition
  body: (block
    (function_definition
      name: (identifier) @name.definition.method)))

; Async functions
(function_definition
  "async" @keyword
  name: (identifier) @name.definition.async_function)

; Decorated functions
(decorated_definition
  (decorator) @decorator
  definition: (function_definition
    name: (identifier) @name.definition.function))

; Decorated classes
(decorated_definition
  (decorator) @decorator
  definition: (class_definition
    name: (identifier) @name.definition.class))

; Lambda functions assigned to variables
(assignment
  left: (identifier) @name.definition.variable
  right: (lambda))

; Global variables (top-level assignments)
(module
  (expression_statement
    (assignment
      left: (identifier) @name.definition.variable)))

; Type aliases (Python 3.10+)
(type_alias
  name: (identifier) @name.definition.type)

; Import statements
(import_statement
  name: (dotted_name
    (identifier) @name.reference.import))

(import_from_statement
  name: (dotted_name
    (identifier) @name.reference.import))

; Imported names
(import_from_statement
  (aliased_import
    name: (identifier) @name.reference.import
    alias: (identifier) @name.definition.import_alias))

(import_from_statement
  name: (identifier) @name.reference.import)

; Function parameters (useful for understanding signatures)
(parameters
  (identifier) @name.definition.parameter)

(default_parameter
  name: (identifier) @name.definition.parameter)

(typed_parameter
  (identifier) @name.definition.parameter)

(typed_default_parameter
  name: (identifier) @name.definition.parameter)

; Dataclass-like decorators
(decorated_definition
  (decorator
    (identifier) @decorator_name
    (#match? @decorator_name "^(dataclass|dataclasses\\.dataclass|attr\\.s|attrs\\.define)$"))
  definition: (class_definition
    name: (identifier) @name.definition.dataclass))

; Property decorators
(decorated_definition
  (decorator
    (attribute
      attribute: (identifier) @decorator_name
      (#match? @decorator_name "^(property|cached_property)$")))
  definition: (function_definition
    name: (identifier) @name.definition.property))

; Class attributes (type annotations in class body)
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @name.definition.attribute))))

; Global constants (UPPER_CASE variables)
(module
  (expression_statement
    (assignment
      left: (identifier) @name.definition.constant
      (#match? @name.definition.constant "^[A-Z_]+$"))))

; Exception definitions
(class_definition
  name: (identifier) @name.definition.exception
  superclasses: (argument_list
    (identifier) @superclass
    (#match? @superclass "^(Exception|Error|Warning)$")))

; Context managers (with statements)
(with_statement
  (with_clause
    (with_item
      value: (identifier) @name.reference.context_manager)))

; Comprehensions
(list_comprehension
  body: (identifier) @name.reference.variable)

(dictionary_comprehension
  body: (pair
    key: (identifier) @name.reference.key
    value: (identifier) @name.reference.value))

(set_comprehension
  body: (identifier) @name.reference.variable)

(generator_expression
  body: (identifier) @name.reference.variable)
