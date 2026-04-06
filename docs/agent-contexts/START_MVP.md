# HorusOne - MVP

> Everything here, is an suggestion, so feel free to change if is required, but try to follow the best practices and patterns.
> Currently, exist some code in this repository, and works fine, maybe can be take as reference or an good starting point, but try to adapt to the new requirements and architecture.

## Mantra

As software architect, i have some mantras that maybe you can follow to create an robust, scalable and well commented codebase.

- Keep simple.
- Follow best practices.
- Follow design patterns.
- Write clean code.
- Write comments when is necessary, but try to make the code self-explanatory.
- Write tests, but try to make them simple and easy to understand.
- Avoid over-engineering, but try to make the code flexible and adaptable to future changes.
- Use version control, and commit often with meaningful messages.
- Document the code, and the architecture decisions, to make it easier for other developers to understand
- Follow design system principles, to create a consistent and cohesive user experience.
- Thinks in the long term, but try to deliver value in the short term, to validate the idea and get feedback from users.
- Thinks in the different layers of the application, and how they interact with each other, to create a modular and maintainable codebase.
- Thinks in the distinct stages: local, staging and production.

## Useful links

Take this as a reference, to create users at distinct stages.

Just like: admin+dashboard@horusone.app, user+seat@horusone.app

Landing page:
- https://horusone.app/

Main domain:
- https://horusone.app/

## Main agents

The follow agents are some suggestions, this is start plan, it's not mandatory used as it. Try to adapt to get the best results,
also, try to eliminate any friction with Github Copilot. As you know, some models have better results with some patterns,
try to adapt to that to get the best results. So, must be place in an well folder separated, and think in Copilot Fleet.

- Document Agent: Responsible for creating and maintaining the documentation, including the architecture decisions, code comments, and any other relevant information. It will ensure that the documentation is up-to-date and easy to understand for other developers.

- Database Agent: Responsible for designing and maintaining the database schema, and ensuring that the database is optimized for performance and scalability. It will also handle any database migrations and ensure that the data is secure. Focus on Postgresql (indexes, partioning, etc) and Redis (caching, pub/sub, etc).
Mongodb can be used for some specific use cases, but try to avoid it if possible, to reduce the complexity of the architecture.

- LangGraph agent: Responsible for designing and maintaining the LangGraph, which is the core of the application. It will ensure that the LangGraph is optimized for performance and scalability, and that it can handle the expected load. It will also handle any updates to the LangGraph, and ensure that it is compatible with the rest of the architecture. Also, is responsible for designing and keep in mind business model.

- Rust Agent: Responsible for business logic, back-end API. Focus on optimization and performance, and real-time features.

- Python Agent: Responsible for the backend, API, and any server-side logic. It will handle data processing, database interactions, and business logic.
Use UV as package manager and FASTAPI as web framework.

- Golang Agent: Responsible for the backend, API, and any server-side logic. It will handle data processing, database interactions, and business logic. Focus on optimization and performance, and real-time features. 

- Front-end Agent: Responsible for the front-end, and any client-side logic. It will handle the user interface, and ensure that it is responsive and user-friendly. It will also handle any interactions with the back-end API, and ensure that the data is displayed correctly. Focus on performance and user experience. Use pnpm as
package manager and Nuxtjs as web framework.

- Devops Agent: Responsible for the deployment and maintenance of the application, including setting up the infrastructure, monitoring, and ensuring that the application is running smoothly. It will also handle any issues that arise in production, and ensure that they are resolved quickly. Docker proeficient, and knowledge in cloud providers (AWS, GCP, Azure) is a plus. Also, is responsible for setting up the CI/CD pipeline, and ensuring that the code is tested and deployed in a timely manner, and scripting for local development environment.

- Keycloak Agent: Responsible for the authentication and authorization of the application, including setting up the Keycloak server, and ensuring that it is properly configured. It will also handle any issues that arise with authentication and authorization, and ensure that they are resolved quickly. It will also handle any integrations with other services that require authentication and authorization.

- Security Agent: Responsible for the security of the application, including identifying and mitigating any potential security risks, and ensuring that the application is secure against common vulnerabilities. It will also handle any security incidents that arise, and ensure that they are resolved quickly. It will also handle any security audits and ensure that the application is compliant with relevant security standards. Keep in mind: organization only can access 
to his own data.

## Business overview

HoruOne is an platform powered by IA (LLM), that's provided an robust, well design and well architecture pilot aviation
training experience, with focus on real time interactions powered by AI (ollama, langgrapg, qdrant, vector and rag).
The main goal of HorusOne, is to provide an immersive and interactive training experience for pilots, that can be used for both commercial and private aviation. The platform will use AI to create realistic scenarios, and provide feedback to the users, to help them improve their skills and knowledge.

- Admin
  The admin will be responsible for managing the platform, including creating and managing organizations, users, and scenarios. The admin will also be responsible for monitoring the platform, and ensuring that it is running smoothly. The admin will have access to all the data in the platform, and will be able to generate reports and analytics to help improve the platform.

- Organization
  An organization can be a flight school, an airline, or any other entity that provides pilot training. Each organization will have its own account, and will be able to create and manage its own scenarios, and users.
  Under this approach, every user must be place in an seat. An organization can be handler a lot of seats -> users
  The basic idea is that organization can have: administrators, instructors, and students (seats).
  Thinks an robust data layer, 'cause an user can be register standalone, and later, can be take part of an organization.

- User (seat)
  A user (seat) is a pilot that is using the platform for training. Each user will have its own account, and will be able to access the scenarios that are assigned to them by their organization. The user will also be able to track their progress, and receive feedback on their performance.

Every session will stored tracking data, that can be use for providing feedback to the users, and also for generating reports and analytics for the organizations. This data can include information about the user's performance, such as their responses to the scenarios, their progress over time, and any areas where they may need improvement. Also, needs well stored data for the scenarios, to ensure that they can be easily accessed and used by the users.

## Architecture overview

> Maybe some layers are missing, another layers can be ruled out, but this is a good starting point, to create a robust and scalable architecture.
> Exist some ideas to implement in the follow iterations: Microsoft Flight Simulator implementation (don't code yet, only keep in mind for flexible and scalable architecture). Also, HorusOne App companion for mobile devices.

- Edge layer
  - Traefik as reverse proxy, to handle the incoming traffic, and route it to the appropriate services. It will also handle SSL termination, and ensure that the traffic is secure.
  - Keycloak for authentication and authorization, to ensure that only authorized users can access the application. It will also handle any integrations with other services that require authentication and authorization.

- Realtime layer
  - Rust and Golang for real-time features, to ensure that the application can handle the expected load, and provide a smooth user experience. It will also handle any interactions with the database, and ensure that the data is processed efficiently.
  - Web socket handlers, to handle real-time interactions between the client and the server, and ensure that the data is transmitted efficiently.
  - Event processing, to handle any events that arise in the application, and ensure that they are processed in a timely manner.

- Control layer:
  - Python for the backend, to handle data processing, database interactions, and business logic. It will also handle any interactions with the front-end, and ensure that the data is displayed correctly.
  - LangGraph for the core of the application, to ensure that the application is optimized for performance and scalability, and that it can handle the expected load. It will also handle any updates to the LangGraph, and ensure that it is compatible with the rest of the architecture.
  - Scenario engine, to handle the creation and management of scenarios, and ensure that they are realistic and interactive. It will also handle any interactions with the database, and ensure that the data is processed efficiently.
  - Llamaindex for vector search, to handle any interactions with the database, and ensure that the data is processed efficiently. It will also handle any updates to the Llamaindex, and ensure that it is compatible with the rest of the architecture.

- Data layer
  - Text-To-Speech, to handle any interactions with the database, and ensure that the data is processed efficiently. It will also handle any updates to the Text-To-Speech, and ensure that it is compatible with the rest of the architecture.
  - Speech-To-Text, to handle any interactions with the database, and ensure that the data is processed efficiently. It will also handle any updates to the Speech-To-Text, and ensure that it is compatible with the rest of the architecture.

