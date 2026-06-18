import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { MessageSquare, Send, AlertCircle } from "lucide-react"
import Markdown from "react-markdown"

interface QueryResponse {
  answer?: string
  entity_id?: string | null
  entity_type?: string | null
  confidence?: number | null
  sources_used?: string[]
  fallback?: boolean
  error?: string
}

function App() {
  const [question, setQuestion] = useState("")
  const [result, setResult] = useState<QueryResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    setResult(null)

    try {
      const res = await fetch("/query/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      })

      const data = await res.json()

      if (!res.ok) {
        setResult({
          error:
            data.detail?.[0]?.msg ||
            data.detail ||
            `Request failed with status ${res.status}`,
        })
      } else {
        setResult(data)
      }
    } catch (err) {
      setResult({
        error:
          err instanceof Error
            ? err.message
            : "Unable to reach the query service.",
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background p-6 md:p-12">
      <div className="mx-auto max-w-3xl space-y-8">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
            Support Memory
          </h1>
          <p className="text-muted-foreground">
            Ask a natural-language question about any customer account.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="size-5" />
              Ask a question
            </CardTitle>
            <CardDescription>
              Examples: “What should the support rep know before calling
              Helios?” or “What changed since the last context build for
              Helios?”
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <Textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Type your question here..."
                rows={4}
                disabled={loading}
              />
              <div className="flex justify-end">
                <Button type="submit" disabled={loading || !question.trim()}>
                  {loading ? (
                    "Thinking..."
                  ) : (
                    <>
                      <Send className="mr-2 size-4" />
                      Ask
                    </>
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {loading && (
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-4/6" />
            </CardContent>
          </Card>
        )}

        {result && !loading && (
          <Card className={result.error ? "border-destructive" : undefined}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {result.error ? (
                  <>
                    <AlertCircle className="size-5 text-destructive" />
                    Error
                  </>
                ) : (
                  "Answer"
                )}
              </CardTitle>
              {!result.error && result.entity_id && (
                <CardDescription>
                  Entity: {" "}
                  <span className="font-medium text-foreground">
                    {result.entity_id}
                  </span>
                  {result.entity_type && ` (${result.entity_type})`}
                  {result.confidence != null && (
                    <>
                      {" · Confidence: "}
                      <span className="font-medium text-foreground">
                        {(result.confidence * 100).toFixed(0)}%
                      </span>
                    </>
                  )}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              {result.error ? (
                <p className="text-sm text-destructive">{result.error}</p>
              ) : (
                <>
                  <div className="prose prose-sm max-w-none text-foreground">
                    <Markdown>{result.answer || ""}</Markdown>
                  </div>
                  {result.fallback && (
                    <p className="text-xs text-muted-foreground">
                      Generated from structured memory fallback.
                    </p>
                  )}
                  {result.sources_used && result.sources_used.length > 0 && (
                    <>
                      <Separator />
                      <div className="space-y-1">
                        <p className="text-xs font-medium text-muted-foreground">
                          Sources used
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {result.sources_used.map((source) => (
                            <span
                              key={source}
                              className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium"
                            >
                              {source}
                            </span>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

export default App
