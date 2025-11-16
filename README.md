# NotebookAgent

## Todo
- fix LLM output rendering, use marked to convert to HTML
- improve how notebook context is formatted for LLM queries
- add ability to edit, delete cells
- add LSP support for code completion & more
- write README that explains how to use and what this is


(maybe, eventually, one day, wishful thinking) 
- upgrade to containers, maybe allow different base images so users can choose a set of libraries that satisfy their needs
- add filesystem persistence?
- append code that has been executed to a file and use a python interpreter to enhance LSP suggestions with existing variables etc
- add a way for multiple people to collaborate on the same notebook
- rework communications from be and fe to sync multiple client communications (e.g propagate write from client1 to all other clients) in a way that reaches eventual consistency
