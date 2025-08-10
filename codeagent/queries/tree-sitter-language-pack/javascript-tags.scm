; JavaScript and JSX tags for code navigation and context
; Captures definitions that can be used for code indexing

; Classes
(class_declaration
  name: (identifier) @name.definition.class)

; Functions
(function_declaration
  name: (identifier) @name.definition.function)

; Arrow functions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.definition.function
    value: (arrow_function)))

; Function expressions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.definition.function
    value: (function_expression)))

; Methods in classes
(method_definition
  name: (property_identifier) @name.definition.method)

; Properties in classes
(field_definition
  property: (property_identifier) @name.definition.property)

; Getters
(method_definition
  name: (property_identifier) @name.definition.getter
  (#match? @name.definition.getter "^get"))

; Setters
(method_definition
  name: (property_identifier) @name.definition.setter
  (#match? @name.definition.setter "^set"))

; Constructors
(method_definition
  name: (property_identifier) @name.definition.constructor
  (#eq? @name.definition.constructor "constructor"))

; Variables/Constants (top-level)
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.definition.variable))

; Variable declarations
(variable_declaration
  (variable_declarator
    name: (identifier) @name.definition.variable))

; Object property assignments (module pattern)
(assignment_expression
  left: (member_expression
    object: (identifier) @name.reference.object
    property: (property_identifier) @name.definition.property))

; Export statements
(export_statement
  declaration: (lexical_declaration
    (variable_declarator
      name: (identifier) @name.definition.export)))

; Named exports
(export_statement
  (export_clause
    (export_specifier
      name: (identifier) @name.definition.export)))

; Import statements
(import_statement
  (import_clause
    (named_imports
      (import_specifier
        name: (identifier) @name.reference.import))))

; JSX Components (capitalized identifiers in JSX)
(jsx_opening_element
  name: (identifier) @name.reference.component
  (#match? @name.reference.component "^[A-Z]"))

(jsx_closing_element
  name: (identifier) @name.reference.component
  (#match? @name.reference.component "^[A-Z]"))

(jsx_self_closing_element
  name: (identifier) @name.reference.component
  (#match? @name.reference.component "^[A-Z]"))
