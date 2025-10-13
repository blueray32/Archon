import React from "react";
import { cn } from "../../../lib/utils";

export interface HexagonCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "neural" | "accent";
  glowing?: boolean;
  animated?: boolean;
}

export const HexagonCard = React.forwardRef<HTMLDivElement, HexagonCardProps>(
  ({ className, variant = "default", glowing = false, animated = false, children, ...props }, ref) => {
    const variantClasses = {
      default: cn(
        "nexarch-glass",
        "border-cyan-400/20 dark:border-cyan-400/30"
      ),
      neural: cn(
        "bg-gradient-to-br from-cyan-500/10 via-purple-500/5 to-pink-500/10",
        "dark:from-cyan-500/15 dark:via-purple-500/10 dark:to-pink-500/15",
        "backdrop-blur-xl",
        "border border-cyan-400/30 dark:border-cyan-400/40",
        "shadow-[0_8px_32px_rgba(0,212,255,0.15),inset_0_1px_0_rgba(255,255,255,0.1)]",
        glowing && "animate-glow-cyan"
      ),
      accent: cn(
        "bg-gradient-to-br from-purple-500/10 to-pink-500/10",
        "dark:from-purple-500/15 dark:to-pink-500/15",
        "backdrop-blur-xl",
        "border border-purple-400/30 dark:border-purple-400/40",
        "shadow-[0_8px_32px_rgba(255,0,255,0.15),inset_0_1px_0_rgba(255,255,255,0.1)]",
        glowing && "animate-glow-purple"
      ),
    };

    return (
      <div
        ref={ref}
        className={cn(
          "relative",
          "rounded-2xl",
          "p-6",
          "transition-all duration-300",
          animated && "hover:scale-[1.02] hover:shadow-2xl",
          variantClasses[variant],
          className
        )}
        {...props}
      >
        {/* Corner hexagon accents */}
        <div className="absolute top-2 left-2 w-3 h-3 hexagon-sm bg-cyan-400/30" />
        <div className="absolute top-2 right-2 w-3 h-3 hexagon-sm bg-purple-400/30" />
        <div className="absolute bottom-2 left-2 w-3 h-3 hexagon-sm bg-pink-400/30" />
        <div className="absolute bottom-2 right-2 w-3 h-3 hexagon-sm bg-cyan-400/30" />

        {/* Content */}
        <div className="relative z-10">{children}</div>

        {/* Animated neural nodes overlay (optional) */}
        {variant === "neural" && (
          <>
            <div
              className="neural-node absolute"
              style={{ top: "15%", left: "10%", animationDelay: "0s" }}
            />
            <div
              className="neural-node-purple absolute"
              style={{ top: "60%", right: "15%", animationDelay: "0.7s" }}
            />
            <div
              className="neural-node-pink absolute"
              style={{ bottom: "20%", left: "20%", animationDelay: "1.4s" }}
            />
          </>
        )}
      </div>
    );
  }
);

HexagonCard.displayName = "HexagonCard";
