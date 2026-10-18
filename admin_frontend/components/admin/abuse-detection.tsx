"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { AbuseDetection } from "@/lib/types";
import { AlertTriangle, Shield, Ban } from "lucide-react";
import { useState } from "react";
import { SuspendWorkspaceModal } from "./suspend-workspace-modal";

interface AbuseDetectionProps {
  abuseDetection: AbuseDetection;
  workspaceName: string;
}

export function AbuseDetectionDisplay({
  abuseDetection,
  workspaceName,
}: AbuseDetectionProps) {
  const [suspendModalOpen, setSuspendModalOpen] = useState(false);
  const { violations, risk_score, recommendations } = abuseDetection;

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "high":
        return "destructive";
      case "medium":
        return "warning";
      case "low":
        return "secondary";
      default:
        return "default";
    }
  };

  const getRiskLevel = (score: number) => {
    if (score >= 0.7) return { label: "High Risk", color: "destructive" };
    if (score >= 0.4) return { label: "Medium Risk", color: "warning" };
    return { label: "Low Risk", color: "secondary" };
  };

  const riskLevel = getRiskLevel(risk_score);

  return (
    <div className="space-y-6">
      {/* Risk Score */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Risk Assessment
          </CardTitle>
          <CardDescription>
            Overall risk score for this workspace
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Risk Score</span>
              <Badge variant={riskLevel.color as any}>
                {riskLevel.label} ({(risk_score * 100).toFixed(0)}%)
              </Badge>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${risk_score * 100}%` }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Violations */}
      {violations && violations.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Violations Detected
            </CardTitle>
            <CardDescription>
              {violations.length} violation{violations.length !== 1 ? "s" : ""}{" "}
              found
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {violations.map((violation, index) => (
                <Alert
                  key={index}
                  variant={
                    violation.severity === "high" ? "destructive" : "default"
                  }
                >
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle className="flex items-center gap-2">
                    {violation.type
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (l) => l.toUpperCase())}
                    <Badge
                      variant={getSeverityColor(violation.severity) as any}
                    >
                      {violation.severity}
                    </Badge>
                  </AlertTitle>
                  <AlertDescription>
                    <p className="mb-2">{violation.description}</p>
                    {violation.threshold && (
                      <p className="text-xs text-muted-foreground">
                        Threshold: {violation.threshold}
                      </p>
                    )}
                    {violation.usage !== undefined &&
                      violation.limit !== undefined && (
                        <p className="text-xs text-muted-foreground">
                          Usage: {violation.usage} / {violation.limit} (
                          {((violation.usage / violation.limit) * 100).toFixed(
                            1
                          )}
                          %)
                        </p>
                      )}
                  </AlertDescription>
                </Alert>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Shield className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-sm font-medium">No violations detected</p>
              <p className="text-xs text-muted-foreground mt-1">
                This workspace appears to be operating normally
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recommendations */}
      {recommendations && recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recommendations</CardTitle>
            <CardDescription>
              Suggested actions based on detected violations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {recommendations.map((recommendation, index) => (
                <li key={index} className="flex items-start gap-2">
                  <span className="text-primary mt-1">•</span>
                  <span className="text-sm">{recommendation}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      {violations && violations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>
              Take immediate action based on detected violations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              variant="destructive"
              onClick={() => setSuspendModalOpen(true)}
            >
              <Ban className="mr-2 h-4 w-4" />
              Suspend Workspace
            </Button>
          </CardContent>
        </Card>
      )}

      <SuspendWorkspaceModal
        workspaceId={abuseDetection.workspace_id}
        workspaceName={workspaceName}
        open={suspendModalOpen}
        onOpenChange={setSuspendModalOpen}
      />
    </div>
  );
}
