import { db } from "./db";
import { threads, messages, type Thread, type Message, type InsertMessage } from "@shared/schema";
import { eq, desc } from "drizzle-orm";

export interface IStorage {
  createThread(title?: string): Promise<Thread>;
  getThreads(): Promise<Thread[]>;
  getThread(id: number): Promise<Thread | undefined>;
  getThreadMessages(threadId: number): Promise<Message[]>;
  createMessage(message: InsertMessage): Promise<Message>;
}

class DatabaseStorage implements IStorage {
  private ensureDb() {
    if (!db) {
      throw new Error("DatabaseStorage requires DATABASE_URL.");
    }
    return db;
  }

  async createThread(title: string = "New Thread"): Promise<Thread> {
    const activeDb = this.ensureDb();
    const [thread] = await activeDb.insert(threads).values({ title }).returning();
    return thread;
  }

  async getThreads(): Promise<Thread[]> {
    const activeDb = this.ensureDb();
    return await activeDb.select().from(threads).orderBy(desc(threads.createdAt));
  }

  async getThread(id: number): Promise<Thread | undefined> {
    const activeDb = this.ensureDb();
    const [thread] = await activeDb.select().from(threads).where(eq(threads.id, id));
    return thread;
  }

  async getThreadMessages(threadId: number): Promise<Message[]> {
    const activeDb = this.ensureDb();
    return await activeDb
      .select()
      .from(messages)
      .where(eq(messages.threadId, threadId))
      .orderBy(messages.createdAt);
  }

  async createMessage(message: InsertMessage): Promise<Message> {
    const activeDb = this.ensureDb();
    const [msg] = await activeDb.insert(messages).values(message).returning();
    return msg;
  }
}

class MemoryStorage implements IStorage {
  private threads: Thread[] = [];
  private messages: Message[] = [];
  private threadCounter = 1;
  private messageCounter = 1;

  async createThread(title: string = "New Thread"): Promise<Thread> {
    const now = new Date();
    const thread: Thread = {
      id: this.threadCounter++,
      title,
      createdAt: now,
    };
    this.threads.unshift(thread);
    return thread;
  }

  async getThreads(): Promise<Thread[]> {
    return [...this.threads];
  }

  async getThread(id: number): Promise<Thread | undefined> {
    return this.threads.find((thread) => thread.id === id);
  }

  async getThreadMessages(threadId: number): Promise<Message[]> {
    return this.messages
      .filter((msg) => msg.threadId === threadId)
      .sort((a, b) => {
        const aTime = a.createdAt ? new Date(a.createdAt).getTime() : 0;
        const bTime = b.createdAt ? new Date(b.createdAt).getTime() : 0;
        return aTime - bTime;
      });
  }

  async createMessage(message: InsertMessage): Promise<Message> {
    const now = new Date();
    const msg: Message = {
      id: this.messageCounter++,
      threadId: message.threadId,
      role: message.role,
      content: message.content,
      sources: message.sources ?? null,
      createdAt: now,
    };
    this.messages.push(msg);
    return msg;
  }
}

// Before example: storage was always Postgres-backed.
// After example: if DATABASE_URL is not set, app still works in-memory for UI testing.
export const storage: IStorage = db ? new DatabaseStorage() : new MemoryStorage();
