"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Copy, ExternalLink } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { get } from "@/lib/api-client";
import { useQuery } from "@tanstack/react-query";
import type { WebhookConfig } from "@/lib/types";

export default function IntegrationsPage() {
  const { toast } = useToast();

  const { data: webhooks } = useQuery<WebhookConfig[]>({
    queryKey: ["webhooks"],
    queryFn: () => get("/api/webhooks"),
  });

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      variant: "success",
      title: "Copied to clipboard",
      description: "Webhook URL copied successfully",
    });
  };

  const webhookUrl =
    webhooks && webhooks.length > 0
      ? `${
          typeof window !== "undefined" ? window.location.origin : ""
        }/api/webhooks/${webhooks[0].id}`
      : "https://your-app.com/api/webhooks/{webhook_id}";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Integrations</h1>
        <p className="text-muted-foreground">
          Connect DocData with your favorite automation tools
        </p>
      </div>

      <Tabs defaultValue="webhooks" className="w-full">
        <TabsList>
          <TabsTrigger value="webhooks">Webhooks</TabsTrigger>
          <TabsTrigger value="make">Make.com</TabsTrigger>
          <TabsTrigger value="zapier">Zapier</TabsTrigger>
          <TabsTrigger value="n8n">n8n</TabsTrigger>
        </TabsList>

        <TabsContent value="webhooks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Webhook Configuration</CardTitle>
              <CardDescription>
                Set up webhooks to receive extraction results automatically
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium mb-2">Webhook URL</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 p-2 bg-muted rounded text-sm">
                    {webhookUrl}
                  </code>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => copyToClipboard(webhookUrl)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="text-sm text-muted-foreground">
                <p className="font-medium mb-1">Available Events:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>extraction.completed - When extraction succeeds</li>
                  <li>extraction.failed - When extraction fails</li>
                  <li>
                    extraction.needs_review - When extraction needs manual
                    review
                  </li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="make" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Make.com Integration</CardTitle>
              <CardDescription>
                Automate workflows with Make.com (formerly Integromat)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h3 className="font-semibold mb-2">Setup Instructions</h3>
                <ol className="list-decimal list-inside space-y-2 text-sm">
                  <li>Create a new scenario in Make.com</li>
                  <li>Add a "Webhooks" → "Custom webhook" trigger</li>
                  <li>Copy your webhook URL from the Webhooks tab</li>
                  <li>Paste the URL in Make.com webhook configuration</li>
                  <li>Select the events you want to listen to</li>
                  <li>
                    Add your DocData API key as a header:{" "}
                    <code className="bg-muted px-1 rounded">
                      Authorization: Bearer YOUR_API_KEY
                    </code>
                  </li>
                </ol>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Sample Payload</h3>
                <pre className="bg-muted p-4 rounded text-xs overflow-auto">
                  {JSON.stringify(
                    {
                      event: "extraction.completed",
                      document_id: "123e4567-e89b-12d3-a456-426614174000",
                      workspace_id: "123e4567-e89b-12d3-a456-426614174000",
                      status: "succeeded",
                      extracted_data: {
                        field1: "value1",
                        field2: "value2",
                      },
                      confidence: 0.95,
                      created_at: "2024-01-01T00:00:00Z",
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Common Use Cases</h3>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>Send extracted data to Google Sheets</li>
                  <li>Create records in CRM systems</li>
                  <li>Send notifications via email or Slack</li>
                  <li>Update databases automatically</li>
                </ul>
              </div>
              <Button asChild>
                <a
                  href="https://www.make.com"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Visit Make.com <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="zapier" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Zapier Integration</CardTitle>
              <CardDescription>
                Connect DocData with 6000+ apps via Zapier
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h3 className="font-semibold mb-2">Setup Instructions</h3>
                <ol className="list-decimal list-inside space-y-2 text-sm">
                  <li>Go to Zapier and create a new Zap</li>
                  <li>Choose "Webhooks by Zapier" as the trigger</li>
                  <li>Select "Catch Hook" trigger event</li>
                  <li>Copy your webhook URL from the Webhooks tab</li>
                  <li>In Zapier, copy the webhook URL provided</li>
                  <li>
                    Update your DocData webhook configuration with the Zapier
                    URL
                  </li>
                  <li>Test the connection by uploading a document</li>
                </ol>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Sample Payload</h3>
                <pre className="bg-muted p-4 rounded text-xs overflow-auto">
                  {JSON.stringify(
                    {
                      event: "extraction.completed",
                      document: {
                        id: "123e4567-e89b-12d3-a456-426614174000",
                        file_name: "invoice.pdf",
                        status: "succeeded",
                      },
                      extraction: {
                        extracted_json: {
                          invoice_number: "INV-001",
                          total: 1000.0,
                        },
                        confidence: 0.95,
                      },
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Common Use Cases</h3>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>Add extracted invoice data to QuickBooks</li>
                  <li>Create tasks in Asana or Trello</li>
                  <li>Send data to Airtable or Notion</li>
                  <li>Trigger email campaigns</li>
                </ul>
              </div>
              <Button asChild>
                <a
                  href="https://zapier.com"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Visit Zapier <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="n8n" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>n8n Integration</CardTitle>
              <CardDescription>
                Self-hosted workflow automation with n8n
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h3 className="font-semibold mb-2">Setup Instructions</h3>
                <ol className="list-decimal list-inside space-y-2 text-sm">
                  <li>Open your n8n instance</li>
                  <li>Create a new workflow</li>
                  <li>Add a "Webhook" node</li>
                  <li>Configure as "POST" method</li>
                  <li>Copy the webhook URL from n8n</li>
                  <li>
                    Update your DocData webhook configuration with the n8n URL
                  </li>
                  <li>
                    Add authentication header:{" "}
                    <code className="bg-muted px-1 rounded">
                      Authorization: Bearer YOUR_API_KEY
                    </code>
                  </li>
                  <li>Test the workflow</li>
                </ol>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Sample Payload</h3>
                <pre className="bg-muted p-4 rounded text-xs overflow-auto">
                  {JSON.stringify(
                    {
                      event: "extraction.completed",
                      document_id: "123e4567-e89b-12d3-a456-426614174000",
                      workspace_id: "123e4567-e89b-12d3-a456-426614174000",
                      template_id: "123e4567-e89b-12d3-a456-426614174000",
                      extracted_data: {
                        field1: "value1",
                        field2: "value2",
                      },
                      metadata: {
                        confidence: 0.95,
                        engine: "tesseract",
                        pages: 1,
                      },
                      timestamp: "2024-01-01T00:00:00Z",
                    },
                    null,
                    2
                  )}
                </pre>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Common Use Cases</h3>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  <li>Process documents and store in local databases</li>
                  <li>Integrate with self-hosted services</li>
                  <li>Custom data transformations</li>
                  <li>Multi-step document processing workflows</li>
                </ul>
              </div>
              <Button asChild>
                <a
                  href="https://n8n.io"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Visit n8n <ExternalLink className="ml-2 h-4 w-4" />
                </a>
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
