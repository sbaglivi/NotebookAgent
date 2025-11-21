Hi, we're building a notebook app.
The backend lives within the be folder, the frontend within the fe folder.
The backend is build in Python with FastAPI, the frontend is vite react-ts.
The persistence layer is just the filesystem right now + in memory objects.
The current focus is integrating a LS (pyright) into the code editor (monaco) that lives in the frontend.
We do not want to use external libraries for the LS integration.