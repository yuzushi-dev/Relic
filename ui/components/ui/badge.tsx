import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "ris-chip inline-flex items-center border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-primary/60 bg-primary/15 text-primary hover:bg-primary/25",
        secondary:
          "border-border bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-destructive/60 bg-destructive/15 text-destructive hover:bg-destructive/25",
        outline: "text-foreground",
        success: "border-success/60 bg-success/15 text-success hover:bg-success/25",
        warning: "border-warning/60 bg-warning/15 text-warning hover:bg-warning/25",
        info: "border-primary/60 bg-primary/15 text-primary hover:bg-primary/25",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
