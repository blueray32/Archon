import React from "react";
import { cn } from "../../../lib/utils";

export interface HexagonButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "neural";
  size?: "sm" | "md" | "lg";
  glowing?: boolean;
}

export const HexagonButton = React.forwardRef<HTMLButtonElement, HexagonButtonProps>(
  ({ className, variant = "primary", size = "md", glowing = false, children, ...props }, ref) => {
    const sizeClasses = {
      sm: "px-4 py-2 text-sm min-w-[100px]",
      md: "px-6 py-3 text-base min-w-[120px]",
      lg: "px-8 py-4 text-lg min-w-[140px]",
    };

    const variantClasses = {
      primary: cn(
        "bg-gradient-to-br from-cyan-500/30 to-purple-500/30",
        "border-2 border-cyan-400/50",
        "hover:from-cyan-500/50 hover:to-purple-500/50",
        "hover:border-cyan-300",
        "text-cyan-100 dark:text-cyan-200",
        glowing && "shadow-[0_0_20px_rgba(0,212,255,0.6),0_0_40px_rgba(255,0,255,0.4)]"
      ),
      secondary: cn(
        "bg-gradient-to-br from-purple-500/30 to-pink-500/30",
        "border-2 border-purple-400/50",
        "hover:from-purple-500/50 hover:to-pink-500/50",
        "hover:border-purple-300",
        "text-purple-100 dark:text-purple-200",
        glowing && "shadow-[0_0_20px_rgba(255,0,255,0.6),0_0_40px_rgba(255,0,128,0.4)]"
      ),
      ghost: cn(
        "bg-transparent",
        "border-2 border-cyan-400/30",
        "hover:bg-cyan-500/10",
        "hover:border-cyan-300/50",
        "text-gray-700 dark:text-gray-300"
      ),
      neural: cn(
        "bg-gradient-to-br from-cyan-500/20 via-purple-500/20 to-pink-500/20",
        "border-2 border-cyan-400/40",
        "hover:from-cyan-500/40 hover:via-purple-500/40 hover:to-pink-500/40",
        "hover:border-cyan-300",
        "text-white",
        "shadow-[0_0_15px_rgba(0,212,255,0.3),0_0_30px_rgba(255,0,255,0.2)]",
        glowing && "animate-glow-cyan"
      ),
    };

    return (
      <div className="relative inline-block" style={{ padding: "2px" }}>
        {/* Hexagonal clip container */}
        <button
          ref={ref}
          className={cn(
            "relative",
            "clip-path-[polygon(30%_0%,_70%_0%,_100%_50%,_70%_100%,_30%_100%,_0%_50%)]",
            "backdrop-blur-md",
            "font-medium",
            "transition-all duration-300 ease-out",
            "hover:scale-105",
            "active:scale-95",
            "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100",
            sizeClasses[size],
            variantClasses[variant],
            className
          )}
          style={{
            clipPath: "polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%)",
          }}
          {...props}
        >
          {/* Inner glow effect */}
          <div
            className="absolute inset-0 opacity-0 hover:opacity-100 transition-opacity duration-300"
            style={{
              clipPath: "polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%)",
              background:
                variant === "primary"
                  ? "radial-gradient(circle at center, rgba(0, 212, 255, 0.3), transparent 70%)"
                  : variant === "secondary"
                  ? "radial-gradient(circle at center, rgba(255, 0, 255, 0.3), transparent 70%)"
                  : variant === "neural"
                  ? "radial-gradient(circle at center, rgba(0, 255, 255, 0.2), rgba(255, 0, 255, 0.2), transparent 70%)"
                  : "radial-gradient(circle at center, rgba(0, 212, 255, 0.1), transparent 70%)",
            }}
          />

          {/* Content */}
          <span className="relative z-10 flex items-center justify-center gap-2">{children}</span>
        </button>
      </div>
    );
  }
);

HexagonButton.displayName = "HexagonButton";
