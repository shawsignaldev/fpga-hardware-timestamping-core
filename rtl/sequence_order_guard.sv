`timescale 1ns/1ps

module sequence_order_guard #(
    parameter int SEQUENCE_WIDTH = 32,
    parameter int TIMESTAMP_WIDTH = 64
) (
    input  logic                         clk,
    input  logic                         rst_n,
    input  logic                         valid_in,
    input  logic [SEQUENCE_WIDTH-1:0]    sequence_in,
    input  logic [TIMESTAMP_WIDTH-1:0]   timestamp,
    output logic                         valid_out,
    output logic                         duplicate,
    output logic                         gap,
    output logic                         out_of_order,
    output logic                         timestamp_regression,
    output logic [SEQUENCE_WIDTH-1:0]    missing_count
);
    logic initialized;
    logic [SEQUENCE_WIDTH-1:0] highest_sequence;
    logic [TIMESTAMP_WIDTH-1:0] highest_timestamp;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            initialized <= 1'b0;
            highest_sequence <= '0;
            highest_timestamp <= '0;
            valid_out <= 1'b0;
            duplicate <= 1'b0;
            gap <= 1'b0;
            out_of_order <= 1'b0;
            timestamp_regression <= 1'b0;
            missing_count <= '0;
        end else begin
            valid_out <= valid_in;
            duplicate <= 1'b0;
            gap <= 1'b0;
            out_of_order <= 1'b0;
            timestamp_regression <= 1'b0;
            missing_count <= '0;

            if (valid_in) begin
                if (!initialized) begin
                    initialized <= 1'b1;
                    highest_sequence <= sequence_in;
                    highest_timestamp <= timestamp;
                end else begin
                    if (sequence_in == highest_sequence) begin
                        duplicate <= 1'b1;
                    end else if (sequence_in > highest_sequence) begin
                        missing_count <= sequence_in - highest_sequence - 1'b1;
                        if ((sequence_in - highest_sequence) > 1) begin
                            gap <= 1'b1;
                        end
                        highest_sequence <= sequence_in;
                    end else begin
                        out_of_order <= 1'b1;
                    end

                    if (timestamp < highest_timestamp) begin
                        timestamp_regression <= 1'b1;
                    end else if (timestamp > highest_timestamp) begin
                        highest_timestamp <= timestamp;
                    end
                end
            end
        end
    end
endmodule
