
import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";
import * as schema from "@shared/schema";

const { Pool } = pg;

// Before example: missing DATABASE_URL crashed server startup.
// After example: app can run in interface tests with in-memory storage fallback.
const connectionString = process.env.DATABASE_URL;

export const pool = connectionString ? new Pool({ connectionString }) : null;
export const db = pool ? drizzle(pool, { schema }) : null;
