"use client";

import { formatDateTime } from "../lib/format";
import type { SubjectIntelligenceData } from "../lib/workbench-data";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./ui/accordion";
import { CheckCircle2, TrendingUp, HelpCircle, Activity, Shield } from "lucide-react";

type Facet = SubjectIntelligenceData["facet_groups"][number]["facets"][number];

function confidenceLevel(c: number): "high" | "medium" | "low" {
  if (c >= 0.7) return "high";
  if (c >= 0.4) return "medium";
  return "low";
}

function FacetRow({ facet }: { facet: Facet }) {
  const positionPct = Math.round(facet.position * 100);
  const confidencePct = Math.round(facet.confidence * 100);
  const level = confidenceLevel(facet.confidence);

  const confidenceColor = 
    level === "high" ? "bg-success" : 
    level === "medium" ? "bg-warning" : 
    "bg-destructive";

  return (
    <div className="py-4 border-b border-border last:border-0 space-y-2">
      <div className="flex justify-between items-center text-xs">
        <span className="font-mono font-semibold text-foreground">{facet.facet}</span>
        <span className="font-mono text-muted-foreground text-[10px] space-x-1">
          <span>pos: <strong className="text-foreground">{facet.position.toFixed(2)}</strong></span>
          <span>•</span>
          <span>conf: <strong className="text-foreground">{facet.confidence.toFixed(2)}</strong></span>
          <span>•</span>
          <span>obs: <strong className="text-foreground">{facet.observations}</strong></span>
        </span>
      </div>

      {/* Track and Needle */}
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-mono">
        <span className="w-20 truncate text-right">{facet.left_anchor}</span>
        <div className="flex-1 relative h-3 bg-muted border border-border rounded-none">
          {/* Position needle */}
          <div 
            className="absolute top-0 bottom-0 w-1 bg-primary hover:scale-x-150 transition-transform cursor-pointer" 
            style={{ left: `${positionPct}%` }}
            title={`Position: ${facet.position}`}
          />
        </div>
        <span className="w-20 truncate">{facet.right_anchor}</span>
      </div>

      {/* Confidence Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[9px] text-muted-foreground font-mono">
          <span>Confidence Indicator</span>
          <span>{confidencePct}%</span>
        </div>
        <div className="h-1.5 w-full bg-muted border border-border rounded-none">
          <div 
            className={`h-full ${confidenceColor}`} 
            style={{ width: `${confidencePct}%` }} 
          />
        </div>
      </div>
    </div>
  );
}

export function SubjectIntelligence({
  subjectIntelligence,
}: {
  subjectIntelligence: SubjectIntelligenceData | null;
}) {
  if (!subjectIntelligence) {
    return (
      <Card className="rounded-none border-destructive bg-destructive/5 mt-4">
        <CardHeader>
          <CardTitle className="text-destructive font-mono text-sm uppercase tracking-wider">
            Behavioral Model Unavailable
          </CardTitle>
          <CardDescription>
            No live behavioral model available for this subject.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground italic">
            Demo intelligence data is intentionally hidden in live mode or profile is incomplete.
          </p>
        </CardContent>
      </Card>
    );
  }

  const summary = subjectIntelligence.model_summary;
  const totalFacets = subjectIntelligence.facet_groups.flatMap((g) => g.facets).length;

  return (
    <div className="space-y-6">
      {/* Model Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { key: "Facets Modeled", val: `${summary.facets_modeled} / ${summary.facets_total}`, icon: Activity },
          { key: "Observations", val: `${summary.seed_observations}`, icon: CheckCircle2 },
          { key: "Signals Extracted", val: `${summary.extraction_signals}`, icon: TrendingUp },
          { key: "Active Hypotheses", val: `${summary.hypotheses}`, icon: Shield },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.key} className="rounded-none border-border">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 p-3 pb-1">
                <CardDescription className="text-[9px] font-semibold uppercase tracking-wider">
                  {item.key}
                </CardDescription>
                <Icon className="h-3.5 w-3.5 text-muted-foreground" />
              </CardHeader>
              <CardContent className="p-3 pt-0">
                <div className="text-xl font-bold font-mono tracking-tight">{item.val}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Tabs Container */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="w-full grid grid-cols-3 rounded-none border border-border p-1 bg-muted/30">
          <TabsTrigger value="overview" className="rounded-none font-mono text-xs py-2">
            Behavioral Overview
          </TabsTrigger>
          <TabsTrigger value="facets" className="rounded-none font-mono text-xs py-2">
            {totalFacets}-Facet Model
          </TabsTrigger>
          <TabsTrigger value="telemetry" className="rounded-none font-mono text-xs py-2">
            Telemetry & Artifacts
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Behavioral Overview */}
        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <Card className="rounded-none border-border md:col-span-8">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Behavioral Summary
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm leading-relaxed text-foreground whitespace-pre-line">
                  {summary.summary}
                </p>
                <div className="pt-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block mb-2">
                    Top Traits Detected
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {subjectIntelligence.top_traits.map((trait) => (
                      <Badge key={trait} variant="secondary" className="rounded-none font-mono text-[10px]">
                        {trait}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-none border-border md:col-span-4">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Active Goals
                </CardTitle>
              </CardHeader>
              <CardContent>
                {subjectIntelligence.active_goals.length > 0 ? (
                  <ul className="space-y-2.5 text-sm list-disc pl-4 text-muted-foreground">
                    {subjectIntelligence.active_goals.map((goal) => (
                      <li key={goal} className="leading-tight">{goal}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground italic font-mono">No explicit goals tracked yet.</p>
                )}
              </CardContent>
            </Card>

            <Card className="rounded-none border-border md:col-span-8">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Cross-Facet Hypotheses
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {subjectIntelligence.hypotheses.length === 0 && (
                  <p className="text-xs text-muted-foreground italic font-mono px-6 py-4">No cross-facet hypotheses yet. Confidence data accumulates from checkin exchanges.</p>
                )}
                <Accordion type="single" collapsible className="w-full">
                  {subjectIntelligence.hypotheses.map((h, i) => {
                    const level = confidenceLevel(h.confidence);
                    const badgeVariant = level === "high" ? "success" : level === "medium" ? "warning" : "destructive";
                    return (
                      <AccordionItem key={h.title} value={`item-${i}`} className="border-b border-border px-6 last:border-0">
                        <AccordionTrigger className="hover:no-underline py-4">
                          <div className="flex items-center justify-between w-full pr-4 text-sm font-medium">
                            <span className="font-mono font-semibold">{h.title}</span>
                            <Badge variant={badgeVariant} className="rounded-none text-[10px]">
                              {h.confidence.toFixed(2)} {h.confidence_label}
                            </Badge>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent className="pb-4 space-y-3">
                          <p className="text-sm text-muted-foreground leading-relaxed">
                            {h.summary}
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {h.facets.map((f) => (
                              <Badge key={f} variant="outline" className="rounded-none font-mono text-[9px] text-muted-foreground">
                                {f}
                              </Badge>
                            ))}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    );
                  })}
                </Accordion>
              </CardContent>
            </Card>

            <Card className="rounded-none border-border md:col-span-4">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Top Confidence Facets
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="divide-y divide-border">
                  {subjectIntelligence.top_confidence_facets.map((facet) => (
                    <div key={facet.facet} className="flex justify-between py-2 first:pt-0 last:pb-0 text-sm">
                      <span className="font-mono text-foreground font-medium">{facet.facet}</span>
                      <div className="font-mono text-xs text-muted-foreground space-x-2">
                        <span>p: {facet.position.toFixed(2)}</span>
                        <span>c: {facet.confidence.toFixed(2)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 2: 18-Facet Model */}
        <TabsContent value="facets" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <Card className="rounded-none border-border md:col-span-8">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  {totalFacets}-Facet Dialectical Model
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {subjectIntelligence.facet_groups.map((group) => (
                  <div key={group.group} className="space-y-3 border-b border-border last:border-0 pb-4 last:pb-0">
                    <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-primary border-l-2 border-primary pl-2 mb-2">
                      {group.group}
                    </h3>
                    <div className="divide-y divide-border">
                      {group.facets.map((facet) => (
                        <FacetRow key={facet.facet} facet={facet} />
                      ))}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="rounded-none border-border md:col-span-4">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Extraction Signals
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {subjectIntelligence.extraction_sample.map((sig, idx) => (
                    <div key={idx} className="p-4 flex flex-col gap-1 hover:bg-muted/10">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-mono font-semibold text-foreground">{sig.facet}</span>
                        <span className="font-mono text-[9px] text-muted-foreground">Strength: {sig.strength.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between items-center text-[10px] text-muted-foreground">
                        <span className="italic">{sig.direction}</span>
                        <code className="bg-muted px-1 border border-border text-[9px]">{sig.source}</code>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 3: Telemetry & Artifacts */}
        <TabsContent value="telemetry" className="mt-4 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <Card className="rounded-none border-border md:col-span-8">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Evidence Transcript Feed
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 max-h-[500px] overflow-y-auto">
                {subjectIntelligence.transcript.length === 0 && (
                  <p className="text-xs text-muted-foreground italic font-mono px-4 py-4">Evidence transcripts not yet extracted. Raw exchange data available in relic.db.</p>
                )}
                <div className="divide-y divide-border">
                  {subjectIntelligence.transcript.map((item) => (
                    <div key={item.id} className="p-4 space-y-2 hover:bg-muted/10">
                      <div className="flex justify-between items-center text-[10px] font-mono text-muted-foreground">
                        <span className="font-semibold text-primary">{item.id}</span>
                        <div className="space-x-2">
                          <Badge variant="outline" className="rounded-none text-[9px] py-0">{item.channel}</Badge>
                          <span>{formatDateTime(item.timestamp)}</span>
                        </div>
                      </div>
                      <p className="text-sm text-foreground leading-relaxed bg-muted/30 p-2.5 border-l border-primary">
                        {item.content}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-none border-border md:col-span-4">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Extraction Information
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Evidence transcripts log natural interaction events. The Gumi runtime continuously analyzes these streams to refine traits and recalibrate model facets.
                </p>
              </CardContent>
            </Card>

            <Card className="rounded-none border-border md:col-span-12">
              <CardHeader>
                <CardTitle className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  Runtime Lineage Artifacts
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead>
                      <tr className="border-b border-border bg-muted/30 font-mono text-xs text-muted-foreground">
                        <th className="p-4 font-semibold uppercase tracking-wider">Artifact Name</th>
                        <th className="p-4 font-semibold uppercase tracking-wider">Type</th>
                        <th className="p-4 font-semibold uppercase tracking-wider">Lineage Origin</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {subjectIntelligence.artifacts.map((artifact) => (
                        <tr key={artifact.name} className="hover:bg-muted/10 font-mono text-xs">
                          <td className="p-4 font-semibold text-foreground">{artifact.name}</td>
                          <td className="p-4 text-muted-foreground">{artifact.kind}</td>
                          <td className="p-4 text-muted-foreground">{artifact.lineage}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
