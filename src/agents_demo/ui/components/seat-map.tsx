"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";

interface SeatMapProps {
    conversationId?: string;
    onSeatSelect: (seatNumber: string) => void;
    selectedSeat?: string;
}

type SeatMapSection = {
    rows: number[];
    seats_per_row: string[];
    occupied: string[];
    exit_rows?: number[];
    premium?: string[];
};

type SeatMapResponse = {
    conversation_id: string;
    flight_number: string;
    aircraft?: string | null;
    sections: Record<string, SeatMapSection>;
    current_seat?: string | null;
};

function getSeatGroups(seats: string[]) {
    const n = seats.length;
    if (n === 4) return [seats.slice(0, 2), seats.slice(2)];
    if (n === 6) return [seats.slice(0, 3), seats.slice(3)];
    if (n === 7) return [seats.slice(0, 2), seats.slice(2, 5), seats.slice(5)];
    if (n === 8) return [seats.slice(0, 2), seats.slice(2, 6), seats.slice(6)];
    if (n === 9) return [seats.slice(0, 3), seats.slice(3, 6), seats.slice(6)];
    const mid = Math.ceil(n / 2);
    return [seats.slice(0, mid), seats.slice(mid)];
}

export function SeatMap({ conversationId, onSeatSelect, selectedSeat }: SeatMapProps) {
    const [seatMap, setSeatMap] = useState<SeatMapResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!conversationId) return;

        let cancelled = false;
        setIsLoading(true);
        setError(null);

        fetch(`/api/seatmap?conversation_id=${encodeURIComponent(conversationId)}`)
            .then((res) => {
                if (!res.ok) throw new Error(`Seat map API error: ${res.status}`);
                return res.json();
            })
            .then((data: SeatMapResponse) => {
                if (cancelled) return;
                setSeatMap(data);
            })
            .catch((err) => {
                if (cancelled) return;
                setError(err?.message || "Failed to load seat map");
            })
            .finally(() => {
                if (cancelled) return;
                setIsLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [conversationId]);

    const currentSeat = (seatMap?.current_seat || "").toUpperCase();
    const selected = (selectedSeat || "").toUpperCase();

    const renderSeatSection = (title: string, section: SeatMapSection | undefined, className: string) => {
        if (!section) return null;
        const occupied = new Set(section.occupied.map((s) => (s || "").toUpperCase()));
        const exitRows = new Set(section.exit_rows || []);
        const premiumSeats = new Set((section.premium || []).map((s) => (s || "").toUpperCase()));
        const seatGroups = getSeatGroups(section.seats_per_row);

        const getSeatStatus = (seatNumber: string) => {
            if (seatNumber === selected) return "selected";
            if (seatNumber === currentSeat) return "current";
            if (occupied.has(seatNumber)) return "occupied";
            return "available";
        };

        const getSeatClassName = (status: string, isExit: boolean, isPremium: boolean) => {
            const base = "w-8 h-8 text-xs font-medium border rounded transition-colors";
            const premiumBorder = isPremium ? " border-blue-300" : "";
            switch (status) {
                case "occupied":
                    return `${base} bg-gray-300 text-gray-500 cursor-not-allowed${premiumBorder}`;
                case "current":
                    return `${base} bg-blue-600 text-white cursor-not-allowed${premiumBorder}`;
                case "selected":
                    return `${base} bg-emerald-600 text-white cursor-pointer hover:bg-emerald-700${premiumBorder}`;
                case "available":
                    return isExit
                        ? `${base} bg-yellow-100 hover:bg-yellow-200 cursor-pointer border-yellow-300${premiumBorder}`
                        : `${base} bg-emerald-100 hover:bg-emerald-200 cursor-pointer border-emerald-300${premiumBorder}`;
                default:
                    return `${base} bg-emerald-100${premiumBorder}`;
            }
        };

        return (
            <div className={`mb-6 ${className}`}>
                <h4 className="text-sm font-semibold mb-2 text-center">{title}</h4>
                <div className="space-y-1">
                    {section.rows.map((row) => {
                        const isExitRow = exitRows.has(row);
                        return (
                            <div key={row} className="flex items-center justify-center gap-1">
                                <span className="w-7 text-xs text-gray-500 text-right mr-2">{row}</span>
                                {seatGroups.map((group, groupIdx) => (
                                    <React.Fragment key={`${row}-${groupIdx}`}>
                                        <div className="flex gap-1">
                                            {group.map((letter) => {
                                                const seatNumber = `${row}${letter}`.toUpperCase();
                                                const status = getSeatStatus(seatNumber);
                                                const isPremium = premiumSeats.has(seatNumber);
                                                const disabled = status === "occupied" || status === "current";
                                                return (
                                                    <button
                                                        key={seatNumber}
                                                        className={getSeatClassName(status, isExitRow, isPremium)}
                                                        onClick={() => status === "available" && onSeatSelect(seatNumber)}
                                                        disabled={disabled}
                                                        title={[
                                                            `Seat ${seatNumber}`,
                                                            isExitRow ? "Exit Row" : null,
                                                            isPremium ? "Premium" : null,
                                                            status === "occupied" ? "Occupied" : null,
                                                            status === "current" ? "Current seat" : null,
                                                        ]
                                                            .filter(Boolean)
                                                            .join(" · ")}
                                                    >
                                                        {letter}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                        {groupIdx < seatGroups.length - 1 && <div className="w-3" />}
                                    </React.Fragment>
                                ))}
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    };

    return (
        <Card className="w-full max-w-md mx-auto my-4 bg-blue-50">
            <CardContent className="p-4">
                <div className="text-center mb-4">
                    <h3 className="font-semibold text-lg mb-1">Select Your Seat</h3>
                    {seatMap?.flight_number && (
                        <p className="text-xs text-gray-600">
                            Flight {seatMap.flight_number}
                            {seatMap.aircraft ? ` · ${seatMap.aircraft}` : ""}
                        </p>
                    )}
                    <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 text-xs mt-3">
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 bg-emerald-100 border border-emerald-300 rounded" />
                            <span>Available</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 bg-gray-300 rounded" />
                            <span>Occupied</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 bg-blue-600 rounded" />
                            <span>Current</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 bg-yellow-100 border border-yellow-300 rounded" />
                            <span>Exit Row</span>
                        </div>
                    </div>
                </div>

                {!conversationId && (
                    <div className="text-sm text-gray-600 text-center py-6">
                        Seat map is unavailable until the conversation starts.
                    </div>
                )}

                {conversationId && isLoading && !seatMap && (
                    <div className="text-sm text-gray-600 text-center py-6">
                        Loading seat map…
                    </div>
                )}

                {conversationId && error && (
                    <div className="text-sm text-red-600 text-center py-6">{error}</div>
                )}

                {seatMap && (
                    <div className="space-y-4">
                        {renderSeatSection("Business Class", seatMap.sections.business, "border-b pb-4")}
                        {renderSeatSection("Economy Class", seatMap.sections.economy, "")}
                    </div>
                )}

                {selected && (
                    <div className="mt-4 p-3 bg-white/70 rounded-lg text-center border border-white/60">
                        <p className="text-sm font-medium text-blue-900">
                            Selected: Seat {selected}
                        </p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
