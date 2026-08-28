---
name: greet
io:
  inputs:
    type: object
    properties:
      name:
        type: string
  outputs:
    type: object
    required: [greeting]
    properties:
      greeting:
        type: string
actions: [greet]
validator: false
---

<action>greet</action>
