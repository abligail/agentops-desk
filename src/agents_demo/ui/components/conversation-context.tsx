"use client";

import { PanelSection } from "./panel-section";
import { Card, CardContent } from "@/components/ui/card";
import { BookText } from "lucide-react";

interface ConversationContextProps {
  context: {
    passenger_name?: string;
    confirmation_number?: string;
    seat_number?: string;
    flight_number?: string;
    account_number?: string;
    meal_preference?: string;
    dietary_restrictions?: string;
    special_requests?: string;
    meal_status?: string;
  };
}

export function ConversationContext({ context }: ConversationContextProps) {
  const contextItems = [
    { key: "passenger_name", label: "Passenger", value: context.passenger_name },
    { key: "account_number", label: "Account", value: context.account_number },
    { key: "confirmation_number", label: "Confirmation", value: context.confirmation_number },
    { key: "flight_number", label: "Flight", value: context.flight_number },
    { key: "seat_number", label: "Seat", value: context.seat_number },
    { key: "meal_preference", label: "Meal", value: context.meal_preference },
    {
      key: "dietary_restrictions",
      label: "Dietary",
      value: context.dietary_restrictions || "none",
    },
    {
      key: "special_requests",
      label: "Special Requests",
      value: context.special_requests || "none",
    },
    {
      key: "meal_status",
      label: "Meal Status",
      value: context.meal_status || "not requested",
    },
  ];

  return (
    <PanelSection
      title="Conversation Context"
      icon={<BookText className="h-4 w-4 text-blue-600" />}
    >
      <Card className="bg-gradient-to-r from-white via-white to-slate-50 border-gray-200 shadow-md">
        <CardContent className="p-3">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            {contextItems.map((item) => (
              <div
                key={item.key}
                className="flex flex-col gap-1 rounded-lg border border-gray-200 bg-white p-2 shadow-sm transition-all"
              >
                <span className="text-[11px] uppercase tracking-wide text-gray-500">
                  {item.label}
                </span>
                <span
                  className={
                    item.value
                      ? "text-sm font-medium text-zinc-900"
                      : "text-sm font-light italic text-gray-400"
                  }
                >
                  {item.value || "pending"}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </PanelSection>
  );
}
