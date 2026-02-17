"""
Prompt templates for transforming raw voice transcriptions into structured coding prompts.
"""

import re


class PromptTemplates:
    """Template-based prompt enhancement for coding tasks."""

    TASK_KEYWORDS = {
        "component": ["component", "widget", "element", "ui", "button", "form", "modal", "dialog", "navbar", "sidebar", "card", "table", "list", "menu", "dropdown", "input", "header", "footer", "layout", "page"],
        "function": ["function", "method", "def", "fn", "helper", "utility", "calculate", "convert", "parse", "format", "validate", "sort", "filter", "transform", "generate", "fetch"],
        "class": ["class", "object", "model", "service", "controller", "repository", "factory", "singleton", "interface"],
        "bug": ["bug", "fix", "debug", "error", "issue", "broken", "crash", "fail", "wrong", "not working", "doesn't work"],
        "refactor": ["refactor", "improve", "optimize", "clean", "restructure", "simplify", "rewrite", "reorganize"],
        "test": ["test", "spec", "unit test", "integration test", "e2e", "coverage", "mock", "assert"],
        "api": ["api", "endpoint", "route", "rest", "graphql", "webhook", "middleware", "request", "response"],
        "database": ["database", "schema", "migration", "query", "table", "sql", "orm", "relation"],
        "style": ["style", "css", "design", "theme", "animation", "responsive", "color", "font"],
        "documentation": ["document", "doc", "comment", "explain", "readme", "guide"],
    }

    FRAMEWORKS = {
        "react": ["react", "jsx", "tsx", "hook", "usestate", "useeffect", "next.js", "nextjs", "redux"],
        "vue": ["vue", "vuejs", "nuxt", "composition api", "vuex", "pinia"],
        "angular": ["angular", "ng", "rxjs", "ngrx"],
        "svelte": ["svelte", "sveltekit"],
        "node": ["node", "express", "fastify", "koa", "nestjs", "deno", "bun"],
        "python": ["python", "django", "flask", "fastapi", "pytorch", "pandas", "numpy"],
        "typescript": ["typescript", "ts", "type", "interface", "generic"],
        "javascript": ["javascript", "js", "es6", "es2015"],
        "rust": ["rust", "cargo", "tokio", "actix"],
        "go": ["go", "golang", "goroutine", "gin"],
        "java": ["java", "spring", "maven", "gradle", "kotlin"],
        "csharp": ["c#", "csharp", "dotnet", ".net", "blazor", "asp.net"],
    }

    @staticmethod
    def detect_task_type(text: str) -> str:
        text_lower = text.lower()
        for task_type, keywords in PromptTemplates.TASK_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return task_type
        return "general"

    @staticmethod
    def detect_framework(text: str) -> str:
        text_lower = text.lower()
        for framework, keywords in PromptTemplates.FRAMEWORKS.items():
            if any(kw in text_lower for kw in keywords):
                return framework
        return "general"

    @staticmethod
    def build_enhanced_prompt(text: str) -> str:
        """Build an enhanced coding prompt from raw voice transcription."""
        text = text.strip()
        if not text:
            return text

        task_type = PromptTemplates.detect_task_type(text)
        framework = PromptTemplates.detect_framework(text)

        parts = []

        if task_type == "bug":
            parts.append(f"Fix the following issue: {text}.")
            parts.append("Identify the root cause, explain the problem, and provide the corrected code.")
        elif task_type == "refactor":
            parts.append(f"Refactor the following: {text}.")
            parts.append("Improve code quality, readability, and maintainability while preserving behavior.")
        elif task_type == "test":
            parts.append(f"Write tests for: {text}.")
            parts.append("Include happy path, edge cases, and error scenarios.")
        elif task_type == "component":
            parts.append(f"Create: {text}.")
            parts.append("Make it reusable with proper props/parameters, accessible, and responsive.")
        elif task_type == "function":
            parts.append(f"Implement: {text}.")
            parts.append("Include type annotations, handle edge cases, and validate inputs.")
        elif task_type == "api":
            parts.append(f"Build: {text}.")
            parts.append("Include request validation, proper status codes, and error handling.")
        elif task_type == "database":
            parts.append(f"Implement: {text}.")
            parts.append("Consider data integrity, indexing, and migration strategy.")
        elif task_type == "documentation":
            parts.append(f"Document: {text}.")
            parts.append("Include description, parameters, return values, and usage examples.")
        elif task_type == "style":
            parts.append(f"Style: {text}.")
            parts.append("Ensure responsive design and accessibility.")
        else:
            parts.append(f"Implement: {text}.")
            parts.append("Follow best practices, include error handling, and add type safety.")

        if framework != "general":
            parts.append(f"Use {framework} conventions and idiomatic patterns.")

        return " ".join(parts)
