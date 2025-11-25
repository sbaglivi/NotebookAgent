# NotebookAgent

In order to fix some issues, I think I need to refactor some key systems in the application. I think the whole notebook state, including cell changes, execution status etc 
should probably live in a centralized spot (what right now is the notebook manager).
Right now I have another project with a deadline that I want to work on, so I'll probably come back to this when I have more time.
Second to last commit should have completions and hover working correctly through the LSP on new code cells, but they weren't properly using the context from earlier
cells because apparently pyright does not fully support the LSP specification for notebooks.

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
