`timescale 1ns/1ps

module timestamp_unwrapper #(
    parameter int COUNTER_WIDTH = 48,
    parameter int EPOCH_WIDTH = 16
) (
    input  logic                                     clk,
    input  logic                                     rst_n,
    input  logic                                     valid_in,
    input  logic [COUNTER_WIDTH-1:0]                 raw_timestamp,
    output logic                                     valid_out,
    output logic [COUNTER_WIDTH+EPOCH_WIDTH-1:0]     unwrapped_timestamp
);
    localparam int TOTAL_WIDTH = COUNTER_WIDTH + EPOCH_WIDTH;
    localparam logic [COUNTER_WIDTH-1:0] HALF_RANGE = {
        1'b1, {(COUNTER_WIDTH-1){1'b0}}
    };

    logic initialized;
    logic [COUNTER_WIDTH-1:0] anchor_raw;
    logic [TOTAL_WIDTH-1:0] anchor_unwrapped;
    logic [EPOCH_WIDTH-1:0] candidate_epoch;
    logic [TOTAL_WIDTH-1:0] candidate_unwrapped;

    always_comb begin
        candidate_epoch = anchor_unwrapped[TOTAL_WIDTH-1:COUNTER_WIDTH];

        if ((raw_timestamp < anchor_raw)
            && ((anchor_raw - raw_timestamp) > HALF_RANGE)) begin
            candidate_epoch = candidate_epoch + 1'b1;
        end else if ((raw_timestamp > anchor_raw)
            && ((raw_timestamp - anchor_raw) >= HALF_RANGE)
            && (candidate_epoch != '0)) begin
            candidate_epoch = candidate_epoch - 1'b1;
        end

        candidate_unwrapped = {candidate_epoch, raw_timestamp};
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            initialized <= 1'b0;
            anchor_raw <= '0;
            anchor_unwrapped <= '0;
            valid_out <= 1'b0;
            unwrapped_timestamp <= '0;
        end else begin
            valid_out <= valid_in;
            if (valid_in) begin
                if (!initialized) begin
                    initialized <= 1'b1;
                    anchor_raw <= raw_timestamp;
                    anchor_unwrapped <= {{EPOCH_WIDTH{1'b0}}, raw_timestamp};
                    unwrapped_timestamp <= {{EPOCH_WIDTH{1'b0}}, raw_timestamp};
                end else begin
                    unwrapped_timestamp <= candidate_unwrapped;
                    if (candidate_unwrapped > anchor_unwrapped) begin
                        anchor_raw <= raw_timestamp;
                        anchor_unwrapped <= candidate_unwrapped;
                    end
                end
            end
        end
    end
endmodule
