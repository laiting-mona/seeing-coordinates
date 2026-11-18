// Where the graph snapshot comes from: a file on disk (local runs, tests), the Worker's static assets, or an R2 object.
// Last edited: 2026-11-18: AssetsGraphSource added (the deployed Worker serves graph.json as a static asset, no R2 needed).

import type { NodeLinkJson } from "../domain/types.js";
import { KnowledgeGraph } from "../graph/KnowledgeGraph.js";

export interface GraphSource {
  load(): Promise<KnowledgeGraph>;
}

/** Reads build/graph.json (Node only; the import is dynamic so the Worker bundle never pulls in fs). */
export class FileGraphSource implements GraphSource {
  constructor(private readonly path: string) {}

  async load(): Promise<KnowledgeGraph> {
    const { readFile } = await import("node:fs/promises");
    const json = JSON.parse(await readFile(this.path, "utf-8")) as NodeLinkJson;
    return KnowledgeGraph.fromNodeLink(json);
  }
}

/** Minimal shape of an R2 bucket binding, so this file needs no Cloudflare type package. */
export interface R2BucketLike {
  get(key: string): Promise<{ text(): Promise<string> } | null>;
}

/** Reads the published snapshot from R2 (the pipeline uploads graph.json there on each release). */
export class R2GraphSource implements GraphSource {
  constructor(private readonly bucket: R2BucketLike, private readonly key = "graph.json") {}

  async load(): Promise<KnowledgeGraph> {
    const object = await this.bucket.get(this.key);
    if (!object) throw new Error(`snapshot ${this.key} not found in R2`);
    return KnowledgeGraph.fromNodeLink(JSON.parse(await object.text()) as NodeLinkJson);
  }
}

/** Minimal shape of the Workers static-assets binding. */
export interface AssetsLike {
  fetch(request: Request | string): Promise<Response>;
}

/** Reads graph.json from the Worker's own static assets (published with the site on each deploy). */
export class AssetsGraphSource implements GraphSource {
  constructor(private readonly assets: AssetsLike, private readonly path = "/graph.json") {}

  async load(): Promise<KnowledgeGraph> {
    const response = await this.assets.fetch(new Request(new URL(this.path, "https://assets.local").toString()));
    if (!response.ok) throw new Error(`snapshot ${this.path} not found in static assets (${response.status})`);
    return KnowledgeGraph.fromNodeLink((await response.json()) as NodeLinkJson);
  }
}
