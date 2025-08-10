; TypeScript and TSX tags for code navigation and context
; Captures definitions that can be used for code indexing

; Classes
(class_declaration
  name: (type_identifier) @name.definition.class)

; Interfaces
(interface_declaration
  name: (type_identifier) @name.definition.interface)

; Type aliases
(type_alias_declaration
  name: (type_identifier) @name.definition.type)

; Enums
(enum_declaration
  name: (identifier) @name.definition.enum)

; Functions
(function_declaration
  name: (identifier) @name.definition.function)

; Function signatures (in .d.ts files)
(function_signature
  name: (identifier) @name.definition.function)

; Arrow functions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @name.definition.function
    value: (arrow_function)))

; Methods in classes
(method_definition
  name: (property_identifier) @name.definition.method)

; Method signatures in interfaces
(method_signature
  name: (property_identifier) @name.definition.method)

; Properties in classes
(public_field_definition
  name: (property_identifier) @name.definition.property)

; Properties in interfaces
(property_signature
  name: (property_identifier) @name.definition.property)

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

; Module declarations
(module
  name: (identifier) @name.definition.module)

(module
  name: (string) @name.definition.module)

; Namespace declarations
(internal_module
  name: (identifier) @name.definition.namespace)

; Export statements with renamed exports
(export_statement
  (export_clause
    (export_specifier
      name: (identifier) @name.definition.export
      alias: (identifier) @name.definition.export)))

; Import statements
(import_statement
  (import_clause
    (named_imports
      (import_specifier
        name: (identifier) @name.reference.import))))

; Generic type parameters
(type_parameter
  name: (type_identifier) @name.definition.type_parameter)
