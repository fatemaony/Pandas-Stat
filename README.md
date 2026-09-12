## Next.js Boilerplate with Better-Auth Enhanced
A robust, production-ready boilerplate for building modern web applications with Next.js 16, Better-Auth, Prisma, and Tailwind CSS.

## Features
Framework: Next.js 16 (App Directory)

Authentication: Better-Auth for secure, type-safe authentication.

Database: Prisma ORM with PostgreSQL.

Styling: Tailwind CSS.

UI Components: Shadcn/UI.

Type Safety: Fully typed with TypeScript.

Icons: Lucide React.

File Uploads: Cloudinary.

Linting & Formatting: ESLint and Prettier configuration.

## Tech Stack
Frontend: React 19, Next.js 16, Tailwind CSS 4
Backend: Next.js Server Actions / API Routes
Database: PostgreSQL (via Prisma)
Auth: Better-Auth (Polished & Type-safe)

## 1. Clone the repository
## 2. Install dependencies
```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

## 3.Environment Setup
Create a .env file in the root directory and add the following variables:
```
#Database
DATABASE_URL=

# Authentication (Better-Auth)
BETTER_AUTH_SECRET=
BETTER_AUTH_URL=
NEXT_PUBLIC_API_URL=

ADMIN_EMAILS=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

#CLOUDINARY(Image upload)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

## 4. Database Setup
Initialize the database schema:
```
npx prisma generate
npx prisma db push
```
## 5.Run the Development Server
```
npm run dev
```
Open http://localhost:3000 to view the application.


## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
