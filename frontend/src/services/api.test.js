import test from "node:test";
import assert from "node:assert/strict";
import { getApiBase } from "./api.js";
import { getWsBase } from "./socket.js";

test("getApiBase should append /api/v1 if not present", () => {
  const result = getApiBase("https://aries-backend-8ydf.onrender.com");
  assert.equal(result, "https://aries-backend-8ydf.onrender.com/api/v1");
});

test("getApiBase should strip trailing slash and append /api/v1", () => {
  const result = getApiBase("https://aries-backend-8ydf.onrender.com/");
  assert.equal(result, "https://aries-backend-8ydf.onrender.com/api/v1");
});

test("getApiBase should preserve existing /api/v1 without duplicate segments", () => {
  const result = getApiBase("https://aries-backend-8ydf.onrender.com/api/v1");
  assert.equal(result, "https://aries-backend-8ydf.onrender.com/api/v1");
});

test("getApiBase should strip trailing slash from existing /api/v1/", () => {
  const result = getApiBase("https://aries-backend-8ydf.onrender.com/api/v1/");
  assert.equal(result, "https://aries-backend-8ydf.onrender.com/api/v1");
});

test("getApiBase should handle localhost without /api/v1", () => {
  const result = getApiBase("http://localhost:8000");
  assert.equal(result, "http://localhost:8000/api/v1");
});

test("getWsBase should convert https to wss with normalized path", () => {
  const ws = getWsBase("https://aries-backend-8ydf.onrender.com");
  assert.equal(ws, "wss://aries-backend-8ydf.onrender.com/api/v1");
});

test("getWsBase should convert http to ws with normalized path", () => {
  const ws = getWsBase("http://localhost:8000/");
  assert.equal(ws, "ws://localhost:8000/api/v1");
});
